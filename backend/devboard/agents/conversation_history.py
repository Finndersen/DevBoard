"""Abstract base interface for conversation history services."""

from abc import ABC, abstractmethod

from devboard.agents.events import ConversationEvent
from devboard.db.models import Conversation
from devboard.db.repositories import ConversationRepository


class ConversationHistoryService(ABC):
    """Abstract base class for conversation history retrieval.

    This interface provides a unified way to retrieve conversation events
    across different agent engines (PydanticAI, Claude Code). It handles
    only history retrieval and does not require agent role information.

    Implementations should handle:
    - Loading conversation history from appropriate storage
    - Converting stored messages to ConversationEvent format
    - Filtering out ephemeral events (e.g., ToolCallRequest)

    Attributes:
        conversation: The conversation instance to retrieve history for
        conversation_repo: Repository for conversation operations
    """

    def __init__(
        self,
        conversation: Conversation,
        conversation_repository: ConversationRepository,
    ):
        """Initialize the conversation history service.

        Args:
            conversation: The conversation instance to retrieve history for
            conversation_repository: Repository for conversation operations
        """
        self.conversation = conversation
        self.conversation_repo = conversation_repository

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
