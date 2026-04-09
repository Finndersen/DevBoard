"""Conversation execution manager for background agent execution."""

import asyncio
import datetime
import time
from collections.abc import AsyncIterator, Coroutine
from pathlib import Path
from typing import Any, Literal, cast

import logfire
from opentelemetry import context as otel_context
from sqlalchemy.orm import Session

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.events import (
    ContextUsage,
    ConversationEvent,
    ExecutionCompleteEvent,
    SystemEvent,
    SystemEventType,
    TextMessage,
)
from devboard.agents.exceptions import AgentInterruptedError, ConversationBusyError
from devboard.agents.execution.agent_execution import AgentExecutionService
from devboard.agents.execution.types import ConversationExecution, ExecutionStatus, SubAgentResult
from devboard.agents.roles.base import AgentRole
from devboard.api.dependencies.factories import create_agent_execution_service, create_agent_role_for_conversation
from devboard.api.dependencies.resolver import DependencyResolver
from devboard.api.dependencies.services import ExecutionServices, get_execution_services
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.database import SessionLocal, get_db
from devboard.db.models import Codebase, Conversation, Project, Task, TaskStatus
from devboard.db.repositories import ConversationRepository
from devboard.db.repositories.log_entry import LogEntryRepository
from devboard.services.project_directory import ensure_project_directory
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_git.service import TaskBranchNotFoundException
from devboard.services.workspace.types import AllSlotsLockedException, BranchInUseException, SetupCommandError


class ConversationExecutionManager:
    """Manages all active agent executions.

    Tracks background task lifecycle and interrupt signaling.
    Keyed by conversation_id — at most one execution per conversation at a time.

    Created and registered during FastAPI lifespan startup via the execution registry.
    """

    def __init__(self) -> None:
        self._executions: dict[int, ConversationExecution] = {}
        self.broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]] = asyncio.Queue()

    async def _run_wrapper(
        self,
        conversation_id: int,
        coro: Coroutine[Any, Any, ContextUsage | None],
    ) -> None:
        """Run the coroutine and handle lifecycle transitions."""
        execution = self._executions.get(conversation_id)
        if not execution:
            raise RuntimeError(f"No execution found for conversation {conversation_id} — this is a programming error")

        # Detach from the request's trace context — background tasks run outside
        # the request lifecycle and should produce their own root span in Logfire.
        token = otel_context.attach(otel_context.Context())
        last_usage: ContextUsage | None = None
        try:
            with logfire.span("background.agent_execution", conversation_id=conversation_id):
                try:
                    last_usage = await coro
                    execution.status = ExecutionStatus.COMPLETED
                    logfire.info(f"Execution completed for conversation {conversation_id}")
                except AgentInterruptedError:
                    execution.status = ExecutionStatus.INTERRUPTED
                    logfire.info(f"Execution interrupted for conversation {conversation_id}")
                except Exception as e:
                    execution.status = ExecutionStatus.FAILED
                    execution.error = str(e)
                    logfire.exception(f"Execution failed for conversation {conversation_id}: {e}")
                finally:
                    execution.completed_at = datetime.datetime.now(datetime.UTC)
                    await self.broadcast_queue.put(
                        (
                            conversation_id,
                            ExecutionCompleteEvent(
                                status=cast(Literal["completed", "interrupted", "failed"], execution.status),
                                error=execution.error,
                                usage=last_usage,
                                timestamp=datetime.datetime.now(datetime.UTC),
                            ),
                        )
                    )
                    self._executions.pop(conversation_id, None)
                    await _emit_agent_run_event(conversation_id, execution.status, execution.error)
        finally:
            otel_context.detach(token)

    def get_execution(self, conversation_id: int) -> ConversationExecution | None:
        return self._executions.get(conversation_id)

    def has_active_execution(self, conversation_id: int) -> bool:
        execution = self._executions.get(conversation_id)
        return execution is not None and execution.status == ExecutionStatus.RUNNING

    def list_active_executions(self, include_sub_agents: bool = False) -> list[ConversationExecution]:
        """Return all currently running executions."""
        return [
            e
            for e in self._executions.values()
            if e.status == ExecutionStatus.RUNNING and (include_sub_agents or not e.is_sub_agent)
        ]

    def start_agent_execution(
        self,
        conversation_id: int,
        message_or_approvals: str | ToolApprovals,
    ) -> ConversationExecution:
        """Start a background agent execution for a conversation.

        Raises:
            ConversationBusyError: If an active execution already exists for this conversation
        """
        existing = self._executions.get(conversation_id)
        if existing and existing.status == ExecutionStatus.RUNNING:
            raise ConversationBusyError(conversation_id)

        interrupt_event = asyncio.Event()

        coro = _run_agent_for_conversation(
            self.broadcast_queue,
            interrupt_event,
            conversation_id=conversation_id,
            message_or_approvals=message_or_approvals,
        )
        task = asyncio.create_task(self._run_wrapper(conversation_id, coro))

        execution = ConversationExecution(
            conversation_id=conversation_id,
            interrupt_requested=interrupt_event,
            asyncio_task=task,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.datetime.now(datetime.UTC),
        )
        self._executions[conversation_id] = execution
        logfire.info(f"Started execution for conversation {conversation_id}")
        return execution

    async def run_sub_agent_execution(
        self,
        conversation: Conversation,
        role: AgentRole,
        prompt: str,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
        working_dir: str,
    ) -> SubAgentResult:
        """Run a sub-agent inline in the calling task, registered for interrupt routing.

        Unlike `start_agent_execution()`, this does not create a new asyncio task — it runs
        inline in the caller's task. However, it registers a `ConversationExecution` entry
        so that `request_interrupt()` can signal it.

        Raises:
            ConversationBusyError: If an active execution already exists for this conversation
        """
        conversation_id = conversation.id
        existing = self._executions.get(conversation_id)
        if existing and existing.status == ExecutionStatus.RUNNING:
            raise ConversationBusyError(conversation_id)

        interrupt_event = asyncio.Event()
        execution = ConversationExecution(
            conversation_id=conversation_id,
            interrupt_requested=interrupt_event,
            asyncio_task=asyncio.current_task(),  # type: ignore[arg-type]
            status=ExecutionStatus.RUNNING,
            started_at=datetime.datetime.now(datetime.UTC),
            is_sub_agent=True,
        )
        parent_execution = self._executions.get(conversation_id)
        self._executions[conversation_id] = execution
        logfire.info(
            f"Starting sub-agent execution for conversation {conversation_id}",
            conversation_id=conversation_id,
            is_sub_agent=True,
            has_parent_execution=parent_execution is not None,
        )
        try:
            with logfire.span("sub_agent_execution", conversation_id=conversation_id, is_sub_agent=True):
                execution_service = create_agent_execution_service(
                    conversation=conversation,
                    role=role,
                    conversation_repo=conversation_repo,
                    agent_config_service=agent_config_service,
                    working_dir=working_dir,
                    interrupt_event=interrupt_event,
                )
                last_text_message: TextMessage | None = None
                async for event in execution_service.stream_events_for_message_or_approval(prompt):
                    conversation_repo.commit()
                    await self.broadcast_queue.put((conversation_id, event))
                    if isinstance(event, TextMessage):
                        last_text_message = event
                conversation_repo.commit()
                await self.broadcast_queue.put(
                    (
                        conversation_id,
                        ExecutionCompleteEvent(
                            status="completed",
                            error=None,
                            timestamp=datetime.datetime.now(datetime.UTC),
                        ),
                    )
                )
                result_text = last_text_message.text_content if last_text_message else ""
                logfire.info(
                    f"Sub-agent execution completed for conversation {conversation_id}",
                    conversation_id=conversation_id,
                    is_sub_agent=True,
                )
                return SubAgentResult(result=result_text, conversation_id=conversation_id)
        finally:
            if parent_execution is not None:
                self._executions[conversation_id] = parent_execution
                logfire.info(
                    f"Restored parent execution for conversation {conversation_id}",
                    conversation_id=conversation_id,
                )
            else:
                self._executions.pop(conversation_id, None)

    def request_interrupt(self, conversation_id: int) -> bool:
        """Request interrupt for the active execution.

        Returns:
            True if an active execution was found and signaled, False otherwise.
        """
        execution = self._executions.get(conversation_id)
        if execution and execution.status == ExecutionStatus.RUNNING:
            execution.interrupt_requested.set()
            logfire.info(
                f"Interrupt requested for conversation {conversation_id}",
                conversation_id=conversation_id,
                is_sub_agent=execution.is_sub_agent,
            )
            return True
        return False


async def _emit_agent_run_event(
    conversation_id: int,
    status: ExecutionStatus,
    error: str | None,
) -> None:
    """Emit an agent_run.completed LogEntry after execution finishes.

    Opens its own DB session since _run_wrapper has no session context.
    Errors are logged but not propagated — emission is a best-effort side effect.
    """
    db = SessionLocal()
    try:
        conversation = ConversationRepository(db).get_by_id(conversation_id)
        if not conversation:
            return
        project_id: int | None = None
        task_id: int | None = None
        parent = conversation.get_parent_entity()
        if isinstance(parent, Task):
            task_id = parent.id
            project_id = parent.project_id
        elif isinstance(parent, Project):
            project_id = parent.id
        SystemEventEmitter(LogEntryRepository(db)).emit_agent_run_completed(
            conversation_id=conversation_id,
            agent_role=conversation.agent_role.value,
            status=status.value,
            project_id=project_id,
            task_id=task_id,
            error=error,
        )
        await asyncio.to_thread(db.commit)
    except Exception:
        logfire.exception(f"Failed to emit agent_run.completed for conversation {conversation_id}")
    finally:
        await asyncio.to_thread(db.close)


async def _drain_events(
    stream: AsyncIterator[ConversationEvent],
    db: Session,
    broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]],
    conversation_id: int,
) -> None:
    async for event in stream:
        t0 = time.monotonic()
        await asyncio.to_thread(db.commit)
        commit_ms = (time.monotonic() - t0) * 1000
        if commit_ms > 200:
            logfire.warn(
                "Slow db.commit in _drain_events",
                conversation_id=conversation_id,
                commit_ms=f"{commit_ms:.0f}",
            )
        await broadcast_queue.put((conversation_id, event))


async def _create_agent_stream(
    services: ExecutionServices,
    conversation: Conversation,
    message_or_approvals: str | ToolApprovals,
    interrupt_event: asyncio.Event,
    working_dir: str,
    additional_write_dirs: list[str] | None = None,
) -> tuple[AsyncIterator[ConversationEvent], AgentExecutionService]:
    """Create an agent execution stream for a conversation.

    Args:
        additional_write_dirs: Extra directories to grant write access to (e.g. the main
            codebase repo dir when working_dir is a worktree).
    """
    role = await create_agent_role_for_conversation(
        conversation=conversation,
        document_repo=services.document_repo,
        agent_config_service=services.agent_config_service,
        integration_service=services.integration_service,
        task_service=services.task_service,
        conversation_repo=services.conversation_repo,
        working_dir=working_dir,
    )
    exec_service = create_agent_execution_service(
        conversation=conversation,
        role=role,
        conversation_repo=services.conversation_repo,
        agent_config_service=services.agent_config_service,
        working_dir=working_dir,
        interrupt_event=interrupt_event,
        additional_write_dirs=additional_write_dirs,
    )
    return exec_service.stream_events_for_message_or_approval(message_or_approvals), exec_service


async def _run_agent_for_conversation(
    broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]],
    interrupt_event: asyncio.Event,
    *,
    conversation_id: int,
    message_or_approvals: str | ToolApprovals,
) -> ContextUsage | None:
    """Run agent execution for a conversation and push events to the broadcast queue.

    Opens its own DB session, constructs services, runs the agent, and pushes
    (conversation_id, ConversationEvent) tuples to the broadcast_queue.
    The ExecutionCompleteEvent is pushed by ConversationExecutionManager._run_wrapper
    after this returns.

    For task conversations, workspace allocation happens first so that the
    role is created with a valid working directory.

    Returns:
        ContextUsage from the agent execution if available, otherwise None.
    """
    db = SessionLocal()
    last_usage: ContextUsage | None = None
    try:
        async with DependencyResolver(dependency_overrides={get_db: lambda: db}) as resolver:
            services = await resolver.run(get_execution_services)
        conversation = services.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        t0 = time.monotonic()
        conversation_parent = conversation.get_parent_entity()
        parent_ms = (time.monotonic() - t0) * 1000
        if parent_ms > 50:
            logfire.warn(
                "Slow get_parent_entity",
                conversation_id=conversation_id,
                parent_ms=f"{parent_ms:.0f}",
            )
        if isinstance(conversation_parent, Task) and conversation_parent.status != TaskStatus.COMPLETE:
            try:
                async with services.workspace_service.allocate_workspace(conversation_parent) as allocation:
                    if not allocation.reused:
                        await broadcast_queue.put(
                            (
                                conversation_id,
                                SystemEvent(
                                    type=SystemEventType.WORKSPACE_ALLOCATE,
                                    data={"task_id": conversation_parent.id, "slot_id": allocation.slot.id},
                                    timestamp=datetime.datetime.now(datetime.UTC),
                                ),
                            )
                        )
                    codebase_local_path = conversation_parent.codebase.local_path
                    additional_write_dirs = (
                        [codebase_local_path] if Path(allocation.slot.path) != Path(codebase_local_path) else None
                    )
                    agent_stream, exec_service = await _create_agent_stream(
                        services,
                        conversation,
                        message_or_approvals,
                        interrupt_event,
                        working_dir=allocation.slot.path,
                        additional_write_dirs=additional_write_dirs,
                    )
                    await _drain_events(
                        services.workspace_service.prepare_workspace(conversation_parent, allocation.slot),
                        db,
                        broadcast_queue,
                        conversation_id,
                    )
                    await _drain_events(agent_stream, db, broadcast_queue, conversation_id)
                    last_usage = exec_service.last_usage
            except BranchInUseException as e:
                await broadcast_queue.put(
                    (
                        conversation_id,
                        SystemEvent(
                            type=SystemEventType.STREAM_ERROR,
                            data={"error_code": "BRANCH_IN_USE", "message": str(e)},
                            timestamp=datetime.datetime.now(datetime.UTC),
                        ),
                    )
                )
            except TaskBranchNotFoundException as e:
                await broadcast_queue.put(
                    (
                        conversation_id,
                        SystemEvent(
                            type=SystemEventType.STREAM_ERROR,
                            data={
                                "error_code": "BRANCH_NOT_FOUND",
                                "message": f"Task branch '{e.branch_name}' does not exist. It may have been deleted or is not available on this machine. Please recreate the branch or fetch it from a remote.",
                            },
                            timestamp=datetime.datetime.now(datetime.UTC),
                        ),
                    )
                )
            except AllSlotsLockedException:
                await broadcast_queue.put(
                    (
                        conversation_id,
                        SystemEvent(
                            type=SystemEventType.STREAM_ERROR,
                            data={
                                "error_code": "SLOTS_EXHAUSTED",
                                "message": "No workspace slots available. Either increase max_worktrees in codebase settings, or wait for an existing task to finish.",
                            },
                            timestamp=datetime.datetime.now(datetime.UTC),
                        ),
                    )
                )
            except SetupCommandError as e:
                await broadcast_queue.put(
                    (
                        conversation_id,
                        SystemEvent(
                            type=SystemEventType.STREAM_ERROR,
                            data={
                                "error_code": "SETUP_COMMAND_FAILED",
                                "message": f"Workspace setup command failed: {e.message}",
                            },
                            timestamp=datetime.datetime.now(datetime.UTC),
                        ),
                    )
                )
            except AgentInterruptedError:
                raise
            except Exception as e:
                logfire.exception(f"Agent execution failed for conversation {conversation_id}: {e}")
                await broadcast_queue.put(
                    (
                        conversation_id,
                        SystemEvent(
                            type=SystemEventType.STREAM_ERROR,
                            data={
                                "error_code": "AGENT_EXECUTION_ERROR",
                                "message": f"Agent execution failed: {e}",
                            },
                            timestamp=datetime.datetime.now(datetime.UTC),
                        ),
                    )
                )
        else:
            if isinstance(conversation_parent, Project):
                working_dir = str(ensure_project_directory(conversation_parent))
            elif isinstance(conversation_parent, Codebase):
                working_dir = conversation_parent.local_path
            else:
                raise ValueError(f"Unsupported parent entity type: {type(conversation_parent).__name__}")

            agent_stream, exec_service = await _create_agent_stream(
                services, conversation, message_or_approvals, interrupt_event, working_dir=working_dir
            )
            await _drain_events(agent_stream, db, broadcast_queue, conversation_id)
            last_usage = exec_service.last_usage

    finally:
        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.close)

    return last_usage
