"""Background execution coroutines for agent conversations.

These coroutines are intended to be run as background asyncio tasks via
ConversationExecutionManager. They manage their own DB sessions since they
cannot use FastAPI's dependency injection directly, using DependencyResolver
with a get_db override to inject the manually-managed session.
"""

import asyncio

from devboard.agents.events import ConversationEvent
from devboard.agents.exceptions import AgentInterruptedError
from devboard.api.dependencies.factories import create_agent_execution_service, create_agent_role_for_conversation
from devboard.api.dependencies.resolver import DependencyResolver
from devboard.api.dependencies.services import get_execution_services
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.database import SessionLocal, get_db
from devboard.db.models import Task, TaskStatus


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

    Args:
        event_queue: Queue to push ConversationEvent objects to
        interrupt_event: Event that signals graceful interrupt should be performed
        conversation_id: ID of the conversation to run the agent for
        message_or_approvals: User message or tool approval decisions
    """
    db = SessionLocal()
    try:
        async with DependencyResolver(dependency_overrides={get_db: lambda: db}) as resolver:
            services = await resolver.run(get_execution_services)
        conversation = services.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        role = await create_agent_role_for_conversation(
            conversation=conversation,
            document_repo=services.document_repo,
            agent_config_service=services.agent_config_service,
            integration_service=services.integration_service,
            task_service=services.task_service,
            task_git_service=services.task_git_service,
            conversation_repo=services.conversation_repo,
        )

        agent_execution_service = create_agent_execution_service(
            conversation=conversation,
            role=role,
            conversation_repo=services.conversation_repo,
            agent_config_service=services.agent_config_service,
            interrupt_event=interrupt_event,
        )

        agent_stream = agent_execution_service.stream_events_for_message_or_approval(message_or_approvals)

        # Wrap with workspace allocation for Task conversations
        conversation_parent = conversation.get_parent_entity()
        if isinstance(conversation_parent, Task) and conversation_parent.status != TaskStatus.COMPLETE:
            agent_stream = services.workspace_allocation_service.run_task_agent_in_workspace(
                task=conversation_parent, agent_stream=agent_stream
            )

        async for event in agent_stream:
            await asyncio.to_thread(db.commit)
            await event_queue.put(event)

        await asyncio.to_thread(db.commit)
    except AgentInterruptedError:
        await asyncio.to_thread(db.commit)
        raise
    except Exception:
        await asyncio.to_thread(db.rollback)
        raise
    finally:
        await asyncio.to_thread(db.close)
