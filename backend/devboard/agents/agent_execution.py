"""Abstract base interface for agent execution services."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import logfire
from pydantic_ai import Tool

from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.events import ConversationEvent
from devboard.agents.roles.base import AgentRole
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.models import Conversation
from devboard.db.repositories import ConversationRepository


class AgentExecutionService(ABC):
    """Abstract base class for agent execution services.

    This interface handles agent execution operations, including sending messages
    and processing tool approvals. It composes a ConversationHistoryService for
    retrieving conversation history when needed.

    Implementations should handle:
    - Agent initialization and configuration
    - Message/approval processing
    - Tool approval workflows
    - Response formatting and event streaming

    Attributes:
        conversation: The conversation instance this service manages
        role: The Role defining agent behavior
        conversation_repo: Repository for conversation operations
        additional_tools: Extra tools beyond those defined by the role
    """

    def __init__(
        self,
        conversation: Conversation,
        role: AgentRole,
        conversation_repository: ConversationRepository,
        history_service: ConversationHistoryService,
        additional_tools: list[Tool] | None = None,
    ):
        """Initialize the agent execution service.

        Args:
            conversation: The conversation instance to manage
            role: The Role defining agent behavior
            conversation_repository: Repository for conversation operations
            history_service: Service for retrieving conversation history
            additional_tools: Optional list of additional tools to provide to the agent,
                beyond those defined by the role. Used for workflow-action-specific tools.
        """
        self.conversation = conversation
        self.role = role
        self.conversation_repo = conversation_repository
        self._history_service = history_service
        self.additional_tools = additional_tools or []

    async def send_message_or_approval(
        self,
        message_or_approvals: str | ToolApprovals,
    ) -> list[ConversationEvent]:
        """Send a message or process tool approvals through the agent.

        Wraps the streaming method to collect all events into a list.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model

        Returns:
            List of conversation events generated during agent execution
        """
        is_approval = isinstance(message_or_approvals, ToolApprovals)

        with logfire.span(
            "agent_execution.send_message_or_approval",
            conversation_id=self.conversation.id,
            is_approval=is_approval,
        ):
            # Collect all events from the stream
            events: list[ConversationEvent] = []
            async for event in self.stream_events_for_message_or_approval(message_or_approvals):
                events.append(event)
            return events

    @abstractmethod
    async def stream_events_for_message_or_approval(
        self,
        message_or_approvals: str | ToolApprovals,
    ) -> AsyncIterator[ConversationEvent]:
        """Stream conversation events from agent execution.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model

        Yields:
            ConversationEvent instances as they are generated during agent execution
        """
        if False:
            yield  # type: ignore[unreachable]  # Required for async generator type inference
