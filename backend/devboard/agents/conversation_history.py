"""Abstract base interface for conversation history services."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from fastapi import HTTPException

from devboard.agents.events import ContextUsage, ConversationEvent
from devboard.db.models import Conversation
from devboard.db.repositories import ConversationRepository


@dataclass
class ConversationHistory:
    """Result of loading conversation history, including messages and usage metadata."""

    messages: list[ConversationEvent] = field(default_factory=lambda: [])
    context_usage: ContextUsage | None = None


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
        self.conversation = conversation
        self.conversation_repo = conversation_repository

    @abstractmethod
    async def get_conversation_history(self) -> ConversationHistory:
        """Retrieve all events and context usage for the conversation.

        Events include text messages, tool calls, and tool results in chronological order.
        Context usage is extracted from the most recent model response during the same
        data load, avoiding redundant reads.

        Returns:
            ConversationHistory with messages in chronological order and optional context usage.
            Note: ToolCallRequest events are excluded as they are ephemeral approval
            requests, not conversation history.
        """
        pass


def create_conversation_history_service(
    conversation: Conversation,
    conversation_repo: ConversationRepository,
) -> "ConversationHistoryService":
    """Create the appropriate history service based on engine type.

    Non-dependency helper that can be called directly from any context.

    Args:
        conversation: The conversation instance
        conversation_repo: Repository for conversation operations

    Returns:
        ConversationHistoryService instance (PydanticAI or ClaudeCode)

    Raises:
        HTTPException: If engine type is unsupported
    """
    # Lazy imports to avoid circular dependency: tools → conversation_history → engines → tools
    from devboard.agents.engines import AgentEngine
    from devboard.agents.engines.claude_code import ClaudeCodeConversationHistoryService
    from devboard.agents.engines.codex import CodexConversationHistoryService
    from devboard.agents.engines.internal import PydanticAIConversationHistoryService

    if conversation.engine == AgentEngine.INTERNAL:
        return PydanticAIConversationHistoryService(
            conversation=conversation,
            conversation_repository=conversation_repo,
        )
    elif conversation.engine == AgentEngine.CLAUDE_CODE:
        return ClaudeCodeConversationHistoryService(
            conversation=conversation,
            conversation_repository=conversation_repo,
        )
    elif conversation.engine == AgentEngine.CODEX:
        return CodexConversationHistoryService(
            conversation=conversation,
            conversation_repository=conversation_repo,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported engine: {conversation.engine}",
        )
