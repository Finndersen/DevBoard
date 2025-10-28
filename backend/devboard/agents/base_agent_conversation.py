"""Abstract base interface for agent conversation services."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import logfire

from devboard.agents.events import ConversationEvent
from devboard.agents.roles.base import Role
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.models import Conversation
from devboard.db.repositories import ConversationRepository


class BaseAgentConversationService(ABC):
    """Abstract base class for agent conversation services.

    This interface allows different agent engines (PydanticAI, Claude Code)
    to be used interchangeably via a unified API.

    Implementations should handle:
    - Agent initialization and configuration
    - Conversation state management (message history or session ID)
    - Tool approval workflows
    - Response formatting
    - Event retrieval

    Attributes:
        conversation: The conversation instance this service manages
        role: The Role defining agent behavior
    """

    def __init__(
        self,
        conversation: Conversation,
        role: Role,
        conversation_repository: ConversationRepository,
    ):
        """Initialize the conversation service with a conversation instance.

        Args:
            conversation: The conversation instance to manage
            role: The Role defining agent behavior
            conversation_repository: Repository for conversation operations
        """
        self.conversation = conversation
        self.role = role
        self.conversation_repo = conversation_repository

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
            "agent_conversation.send_message_or_approval",
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
        pass

    @abstractmethod
    async def get_conversation_messages(self) -> list[ConversationEvent]:
        """Retrieve all events for the conversation.

        Events include text messages, tool calls, and tool results in chronological order.
        This provides a complete timeline of the conversation including intermediate steps.

        For PydanticAI conversations, events are queried from the database.
        For external engines (Claude Code, Gemini CLI), events are loaded
        from their respective session storage.

        Returns:
            List of ConversationEvent instances (ConversationMessage, ToolCall, ToolResult)
            in chronological order.
            Note: ToolCallRequest events are excluded as they are ephemeral approval
            requests, not conversation history.
        """
        pass
