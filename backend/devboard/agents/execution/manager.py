"""Conversation execution manager for background agent execution."""

import asyncio
import datetime
import time
from collections.abc import AsyncIterator, Coroutine
from pathlib import Path
from typing import Any, Literal

import logfire
from opentelemetry import context as otel_context
from sqlalchemy.orm import Session

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.events import (
    AgentRunCompletedEvent,
    ConversationEvent,
    SystemEvent,
    SystemEventType,
    TextMessage,
)
from devboard.agents.exceptions import AgentInterruptedError, ConversationBusyError, SubAgentRateLimitError
from devboard.agents.execution.types import ConversationExecution, ExecutionStatus, SubAgentResult
from devboard.agents.roles.base import AgentRole
from devboard.api.dependencies.factories import create_agent_execution_service, create_agent_role_for_conversation
from devboard.api.dependencies.resolver import DependencyResolver
from devboard.api.dependencies.services import ExecutionServices, get_execution_services
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.database import SessionLocal, get_db
from devboard.db.models import (
    BackgroundAgent,
    BackgroundAgentRunStatus,
    Codebase,
    Conversation,
    Project,
    Task,
    TaskStatus,
)
from devboard.db.repositories import ConversationRepository, LogEntryRepository
from devboard.db.repositories.background_agent import BackgroundAgentRunRepository
from devboard.db.session_lock import commit_with_lock
from devboard.services.background_agent_directory import ensure_background_agent_directory
from devboard.services.project_directory import ensure_project_directory
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_git.service import TaskBranchNotFoundException
from devboard.services.workspace.types import AllSlotsLockedException, BranchInUseException, SetupCommandError


class ConversationExecutionManager:
    """Process-wide registry of active agent executions.

    Tracks all in-flight runs via `_executions` (conversation_id → ConversationExecution),
    owns the `broadcast_queue` consumed by the WebSocket fan-out, routes interrupt signals,
    and enforces at-most-one execution per conversation. Singleton created during FastAPI
    lifespan startup.
    """

    def __init__(self) -> None:
        self._executions: dict[int, ConversationExecution] = {}
        self.broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]] = asyncio.Queue()

    async def _run_wrapper(
        self,
        conversation_id: int,
        coro: Coroutine[Any, Any, None],
    ) -> None:
        """Run the coroutine and handle lifecycle transitions.

        Drives execution status on the ConversationExecution entry and detaches
        the OTel trace context. All broadcast events (including ExecutionCompleteEvent)
        are emitted by _run_agent_for_conversation.
        """
        execution = self._executions.get(conversation_id)
        if not execution:
            raise RuntimeError(f"No execution found for conversation {conversation_id} — this is a programming error")

        # Detach from the request's trace context — background tasks run outside
        # the request lifecycle and should produce their own root span in Logfire.
        token = otel_context.attach(otel_context.Context())
        try:
            with logfire.span("background.agent_execution", conversation_id=conversation_id):
                try:
                    await coro
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
                    self._finalize_execution(conversation_id)
        finally:
            otel_context.detach(token)

    def _finalize_execution(self, conversation_id: int) -> None:
        execution = self._executions.pop(conversation_id, None)
        if execution is not None:
            execution.completed_at = datetime.datetime.now(datetime.UTC)

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
        effort: Literal["low", "medium", "high"] | None = None,
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
        current_task = asyncio.current_task()
        assert current_task is not None, (
            "register_sub_agent_execution must be called from within a running asyncio task"
        )
        execution = ConversationExecution(
            conversation_id=conversation_id,
            interrupt_requested=interrupt_event,
            asyncio_task=current_task,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.datetime.now(datetime.UTC),
            is_sub_agent=True,
        )
        self._executions[conversation_id] = execution
        logfire.info(
            f"Starting sub-agent execution for conversation {conversation_id}",
            conversation_id=conversation_id,
            is_sub_agent=True,
        )
        try:
            with logfire.span("sub_agent_execution", conversation_id=conversation_id, is_sub_agent=True):
                try:
                    execution_service = create_agent_execution_service(
                        conversation=conversation,
                        role=role,
                        conversation_repo=conversation_repo,
                        agent_config_service=agent_config_service,
                        working_dir=working_dir,
                        interrupt_event=interrupt_event,
                        effort=effort,
                    )
                    last_text_message: TextMessage | None = None
                    async for event in execution_service.stream_events_for_message_or_approval(prompt):
                        conversation_repo.commit()
                        await self.broadcast_queue.put((conversation_id, event))
                        if isinstance(event, TextMessage):
                            last_text_message = event
                    conversation_repo.commit()
                    result_text = last_text_message.text_content if last_text_message else ""

                    # Check for rate-limit responses: both conditions must be met
                    if (
                        last_text_message is not None
                        and last_text_message.model == "<synthetic>"
                        and "You've hit your limit" in result_text
                    ):
                        raise SubAgentRateLimitError(f"Sub-agent hit rate limit: {result_text}")

                    execution.status = ExecutionStatus.COMPLETED
                    logfire.info(
                        f"Sub-agent execution completed for conversation {conversation_id}",
                        conversation_id=conversation_id,
                        is_sub_agent=True,
                    )
                    return SubAgentResult(result=result_text, conversation_id=conversation_id)
                except AgentInterruptedError:
                    execution.status = ExecutionStatus.INTERRUPTED
                    logfire.info(
                        f"Sub-agent execution interrupted for conversation {conversation_id}",
                        conversation_id=conversation_id,
                        is_sub_agent=True,
                    )
                    raise
                except Exception as e:
                    execution.status = ExecutionStatus.FAILED
                    execution.error = str(e)
                    logfire.exception(
                        f"Sub-agent execution failed for conversation {conversation_id}: {e}",
                        conversation_id=conversation_id,
                        is_sub_agent=True,
                    )
                    raise
        finally:
            self._finalize_execution(conversation_id)

    async def broadcast_event(
        self,
        conversation_id: int,
        event: ConversationEvent,
    ) -> None:
        """Broadcast a ConversationEvent on the given conversation's WebSocket stream."""
        await self.broadcast_queue.put((conversation_id, event))

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


async def _drain_events(
    stream: AsyncIterator[ConversationEvent],
    db: Session,
    broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]],
    conversation_id: int,
) -> AgentRunCompletedEvent | None:
    completed_event: AgentRunCompletedEvent | None = None
    async for event in stream:
        if isinstance(event, AgentRunCompletedEvent):
            completed_event = event
        t0 = time.monotonic()
        await asyncio.to_thread(commit_with_lock, db)
        commit_ms = (time.monotonic() - t0) * 1000
        if commit_ms > 200:
            logfire.warn(
                "Slow db.commit in _drain_events",
                conversation_id=conversation_id,
                commit_ms=f"{commit_ms:.0f}",
            )
        await broadcast_queue.put((conversation_id, event))
    return completed_event


async def _create_agent_stream(
    services: ExecutionServices,
    conversation: Conversation,
    message_or_approvals: str | ToolApprovals,
    interrupt_event: asyncio.Event,
    working_dir: str,
    additional_write_dirs: list[str] | None = None,
) -> AsyncIterator[ConversationEvent]:
    """Create an agent execution stream for a conversation.

    The returned stream includes lifecycle events:
    `AgentRunStartedEvent` as the first event and `AgentRunCompletedEvent` as the last.

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
    return exec_service.stream_events_for_message_or_approval(message_or_approvals)


async def _emit_stream_error(
    broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]],
    conversation_id: int,
    error_code: str,
    message: str,
) -> None:
    """Broadcast a STREAM_ERROR SystemEvent for the given conversation."""
    await broadcast_queue.put(
        (
            conversation_id,
            SystemEvent(
                sub_type=SystemEventType.STREAM_ERROR,
                data={"error_code": error_code, "message": message},
                timestamp=datetime.datetime.now(datetime.UTC),
            ),
        )
    )


def _resolve_background_agent_working_dir(agent: BackgroundAgent, db: Session) -> str:
    """Resolve the working directory for a background agent execution."""
    if agent.project_id is not None:
        project = db.get(Project, agent.project_id)
        if project is None:
            raise ValueError(f"Project {agent.project_id} not found for background agent {agent.id}")
        if project.codebases:
            return project.codebases[0].local_path
        return str(ensure_project_directory(project))
    return str(ensure_background_agent_directory(agent))


def _map_execution_status_to_run_status(status: ExecutionStatus) -> BackgroundAgentRunStatus:
    match status:
        case ExecutionStatus.COMPLETED:
            return BackgroundAgentRunStatus.COMPLETED
        case ExecutionStatus.INTERRUPTED:
            return BackgroundAgentRunStatus.CANCELLED
        case ExecutionStatus.FAILED:
            return BackgroundAgentRunStatus.FAILED
        case _:
            raise ValueError(f"Unhandled execution status: {status}")


async def _run_task_agent(
    services: ExecutionServices,
    conversation: Conversation,
    task: Task,
    message_or_approvals: str | ToolApprovals,
    interrupt_event: asyncio.Event,
    db: Session,
    broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]],
    conversation_id: int,
) -> None:
    """Allocate a workspace for the task and run the agent within it.

    Handles workspace-allocation-specific errors by broadcasting STREAM_ERROR
    SystemEvents; all other errors propagate to the caller.
    """
    try:
        async with services.workspace_service.allocate_workspace(task) as allocation:
            if not allocation.reused:
                await broadcast_queue.put(
                    (
                        conversation_id,
                        SystemEvent(
                            sub_type=SystemEventType.WORKSPACE_ALLOCATE,
                            data={"task_id": task.id, "slot_id": allocation.slot.id},
                            timestamp=datetime.datetime.now(datetime.UTC),
                        ),
                    )
                )
            codebase_local_path = task.codebase.local_path
            additional_write_dirs = (
                [codebase_local_path] if Path(allocation.slot.path) != Path(codebase_local_path) else None
            )
            agent_stream = await _create_agent_stream(
                services,
                conversation,
                message_or_approvals,
                interrupt_event,
                working_dir=allocation.slot.path,
                additional_write_dirs=additional_write_dirs,
            )
            # Allocate workspace and emit any relevant events
            await _drain_events(
                services.workspace_service.prepare_workspace(task, allocation.slot),
                db,
                broadcast_queue,
                conversation_id,
            )
            # Run agent stream loop and emit events until completion or error
            await _drain_events(agent_stream, db, broadcast_queue, conversation_id)
    except BranchInUseException as e:
        await _emit_stream_error(broadcast_queue, conversation_id, "BRANCH_IN_USE", str(e))
    except TaskBranchNotFoundException as e:
        await _emit_stream_error(
            broadcast_queue,
            conversation_id,
            "BRANCH_NOT_FOUND",
            f"Task branch '{e.branch_name}' does not exist. It may have been deleted or is not available on this machine. Please recreate the branch or fetch it from a remote.",
        )
    except AllSlotsLockedException:
        await _emit_stream_error(
            broadcast_queue,
            conversation_id,
            "SLOTS_EXHAUSTED",
            "No workspace slots available. Either increase max_worktrees in codebase settings, or wait for an existing task to finish.",
        )
    except SetupCommandError as e:
        await _emit_stream_error(
            broadcast_queue,
            conversation_id,
            "SETUP_COMMAND_FAILED",
            f"Workspace setup command failed: {e.message}",
        )
    except AgentInterruptedError:
        raise
    except Exception as e:
        logfire.exception(f"Agent execution failed for conversation {conversation_id}: {e}")
        await _emit_stream_error(
            broadcast_queue,
            conversation_id,
            "AGENT_EXECUTION_ERROR",
            f"Agent execution failed: {e}",
        )


async def _run_agent_for_conversation(
    broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]],
    interrupt_event: asyncio.Event,
    *,
    conversation_id: int,
    message_or_approvals: str | ToolApprovals,
) -> None:
    """Run agent execution for a conversation and push events to the broadcast queue.

    Opens its own DB session, commits `update_last_activity` before the stream starts
    (so `last_activity_at` is persisted before `AgentRunStartedEvent` reaches the
    frontend), allocates a workspace for task conversations, drains the agent stream
    into the broadcast queue, and writes the `agent_run.completed` LogEntry.
    """
    db = SessionLocal()
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    error: str | None = None
    completed_event: AgentRunCompletedEvent | None = None
    conversation_parent: Task | Project | Codebase | BackgroundAgent | None = None

    async with DependencyResolver(dependency_overrides={get_db: lambda: db}) as resolver:
        services = await resolver.run(get_execution_services)
    conversation = services.conversation_repo.get_by_id(conversation_id)
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found")

    try:
        # ── Start-of-run side effects (shared session) ──────────────────────
        # Commit before the stream starts so last_activity_at is persisted before
        # AgentRunStartedEvent (the first event from the stream) reaches the frontend.
        services.conversation_repo.update_last_activity(conversation)
        await asyncio.to_thread(commit_with_lock, db)

        # ── Agent execution ─────────────────────────────────────────────────
        try:
            conversation_parent = conversation.get_parent_entity()
            if isinstance(conversation_parent, Task):
                if conversation_parent.status == TaskStatus.COMPLETE:
                    raise ValueError(
                        f"Cannot run agent for completed task {conversation_parent.id} (conversation {conversation_id})"
                    )
                await _run_task_agent(
                    services,
                    conversation,
                    conversation_parent,
                    message_or_approvals,
                    interrupt_event,
                    db,
                    broadcast_queue,
                    conversation_id,
                )
            elif isinstance(conversation_parent, Project):
                working_dir = str(ensure_project_directory(conversation_parent))
                agent_stream = await _create_agent_stream(
                    services, conversation, message_or_approvals, interrupt_event, working_dir=working_dir
                )
                await _drain_events(agent_stream, db, broadcast_queue, conversation_id)
            elif isinstance(conversation_parent, Codebase):
                working_dir = conversation_parent.local_path
                agent_stream = await _create_agent_stream(
                    services, conversation, message_or_approvals, interrupt_event, working_dir=working_dir
                )
                await _drain_events(agent_stream, db, broadcast_queue, conversation_id)
            elif isinstance(conversation_parent, BackgroundAgent):  # pyright: ignore[reportUnnecessaryIsInstance]
                working_dir = _resolve_background_agent_working_dir(conversation_parent, db)
                agent_stream = await _create_agent_stream(
                    services, conversation, message_or_approvals, interrupt_event, working_dir=working_dir
                )
                completed_event = await _drain_events(agent_stream, db, broadcast_queue, conversation_id)
            else:
                raise ValueError(f"Unsupported parent entity type: {type(conversation_parent).__name__}")
        except AgentInterruptedError:
            status = ExecutionStatus.INTERRUPTED
            raise
        except Exception as e:
            status = ExecutionStatus.FAILED
            error = str(e)
            raise

    finally:
        # ── End-of-run side effects ─────────────────────────────────────────
        # AgentRunCompletedEvent is emitted by AgentExecutionService.stream_events_for_message_or_approval;
        # only the DB log entry is written here.
        try:
            SystemEventEmitter(LogEntryRepository(db)).emit_agent_run_completed(
                conversation=conversation,
                status=status.value,
                error=error,
            )
        except Exception:
            logfire.exception(f"Failed to emit agent_run.completed for conversation {conversation_id}")
        if isinstance(conversation_parent, BackgroundAgent):
            try:
                run = BackgroundAgentRunRepository(db).get_by_conversation_id(conversation_id)
                if run is not None:
                    db.refresh(conversation_parent)
                    run.completed_at = datetime.datetime.now(datetime.UTC)
                    run.status = _map_execution_status_to_run_status(status)
                    run.error = error
                    if completed_event is not None and completed_event.usage is not None:
                        run.input_tokens = completed_event.usage.input_tokens
                        run.output_tokens = completed_event.usage.output_tokens
                    run.state_after = conversation_parent.state
                else:
                    logfire.warning(
                        f"BackgroundAgentRun not found for conversation {conversation_id} during finalization"
                    )
            except Exception:
                logfire.exception(f"Failed to finalize BackgroundAgentRun for conversation {conversation_id}")
        await asyncio.to_thread(commit_with_lock, db)
        await asyncio.to_thread(db.close)
