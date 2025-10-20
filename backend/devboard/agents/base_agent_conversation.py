"""Abstract base interface for agent conversation services."""

from abc import ABC, abstractmethod

from devboard.api.schemas.agent_conversation import ConversationEvent, ToolApprovalDecision
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
    """

    def __init__(self, conversation: Conversation, conversation_repository: ConversationRepository):
        """Initialize the conversation service with a conversation instance.

        Args:
            conversation: The conversation instance to manage
            conversation_repository: Repository for conversation operations
        """
        self.conversation = conversation
        self.conversation_repo = conversation_repository

    @abstractmethod
    async def send_message(self, message: str) -> list[ConversationEvent]:
        """Send a message to the agent and get a response.

        Args:
            message: The user's message

        Returns:
            PromptResponse containing either a message or tool approval requests
        """
        pass

    @abstractmethod
    async def process_tool_approvals(self, approvals: dict[str, ToolApprovalDecision]) -> list[ConversationEvent]:
        """Process user's tool approval decisions and continue agent execution.

        Args:
            approvals: Map of tool_call_id to approval decision

        Returns:
            PromptResponse with agent's next message or additional tool requests
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
