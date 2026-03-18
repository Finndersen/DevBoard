"""Background execution coroutines for agent conversations.

These coroutines are intended to be run as background asyncio tasks via
ConversationExecutionManager. They manage their own DB sessions since they
cannot use FastAPI's dependency injection directly, using DependencyResolver
with a get_db override to inject the manually-managed session.
"""

import asyncio
import datetime
from collections.abc import AsyncIterator

from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType
from devboard.api.dependencies.factories import create_agent_execution_service, create_agent_role_for_conversation
from devboard.api.dependencies.resolver import DependencyResolver
from devboard.api.dependencies.services import ExecutionServices, get_execution_services
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.database import SessionLocal, get_db
from devboard.db.models import Codebase, Project, Task, TaskStatus
from devboard.services.project_directory import ensure_project_directory
from devboard.services.workspace.types import AllSlotsLockedException, BranchInUseException, SetupCommandError


async def _drain_events(
    stream: AsyncIterator[ConversationEvent],
    db,
    event_queue: asyncio.Queue[ConversationEvent | None],
) -> None:
    """Iterate an event stream, committing and enqueuing each event."""
    async for event in stream:
        await asyncio.to_thread(db.commit)
        await event_queue.put(event)


async def _create_agent_stream(
    services: ExecutionServices,
    conversation,
    message_or_approvals: str | ToolApprovals,
    interrupt_event: asyncio.Event,
    working_dir: str,
) -> AsyncIterator[ConversationEvent]:
    """Create the full agent stream: role → execution service → event iterator."""
    role = await create_agent_role_for_conversation(
        conversation=conversation,
        document_repo=services.document_repo,
        agent_config_service=services.agent_config_service,
        integration_service=services.integration_service,
        task_service=services.task_service,
        task_git_service=services.task_git_service,
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
    )
    return exec_service.stream_events_for_message_or_approval(message_or_approvals)


async def run_agent_for_conversation(
    event_queue: asyncio.Queue[ConversationEvent | None],
    interrupt_event: asyncio.Event,
    *,
    conversation_id: int,
    message_or_approvals: str | ToolApprovals,
) -> None:
    """Run agent execution for a conversation and push events to the queue.

    Opens its own DB session, constructs services, runs the agent, and pushes
    ConversationEvent objects to the event_queue. The queue sentinel (None) is
    pushed by the ConversationExecutionManager wrapper after this returns.

    For task conversations, workspace allocation happens first so that the
    role is created with a valid working directory.
    """
    db = SessionLocal()
    try:
        async with DependencyResolver(dependency_overrides={get_db: lambda: db}) as resolver:
            services = await resolver.run(get_execution_services)
        conversation = services.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation_parent = conversation.get_parent_entity()
        is_task = isinstance(conversation_parent, Task) and conversation_parent.status != TaskStatus.COMPLETE

        if is_task:
            try:
                async with services.workspace_service.allocate_workspace(conversation_parent) as slot:
                    agent_stream = await _create_agent_stream(
                        services, conversation, message_or_approvals, interrupt_event, working_dir=slot.path
                    )
                    await _drain_events(
                        services.workspace_service.prepare_workspace(conversation_parent, slot), db, event_queue
                    )
                    await _drain_events(agent_stream, db, event_queue)
            except BranchInUseException as e:
                await event_queue.put(
                    SystemEvent(
                        type=SystemEventType.STREAM_ERROR,
                        data={"error_code": "BRANCH_IN_USE", "message": str(e)},
                        timestamp=datetime.datetime.now(datetime.UTC),
                    )
                )
            except AllSlotsLockedException:
                await event_queue.put(
                    SystemEvent(
                        type=SystemEventType.STREAM_ERROR,
                        data={
                            "error_code": "SLOTS_EXHAUSTED",
                            "message": "No workspace slots available. Either increase max_worktrees in codebase settings, or wait for an existing task to finish.",
                        },
                        timestamp=datetime.datetime.now(datetime.UTC),
                    )
                )
            except SetupCommandError as e:
                await event_queue.put(
                    SystemEvent(
                        type=SystemEventType.STREAM_ERROR,
                        data={
                            "error_code": "SETUP_COMMAND_FAILED",
                            "message": f"Workspace setup command failed: {e.message}",
                        },
                        timestamp=datetime.datetime.now(datetime.UTC),
                    )
                )
        else:
            if isinstance(conversation_parent, Project):
                working_dir = str(ensure_project_directory(conversation_parent))
            elif isinstance(conversation_parent, Codebase):
                working_dir = conversation_parent.local_path
            else:
                raise ValueError(f"Unsupported parent entity type: {type(conversation_parent).__name__}")

            agent_stream = await _create_agent_stream(
                services, conversation, message_or_approvals, interrupt_event, working_dir=working_dir
            )
            await _drain_events(agent_stream, db, event_queue)

    finally:
        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.close)
