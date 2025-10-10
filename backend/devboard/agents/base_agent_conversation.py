"""Abstract base interface for agent conversation services."""

from abc import ABC, abstractmethod

from devboard.api.schemas.agent_conversation import PromptResponse, ToolApprovalDecision


class BaseAgentConversationService(ABC):
    """Abstract base class for agent conversation services.

    This interface allows different agent engines (PydanticAI, Claude Code)
    to be used interchangeably via a unified API.

    Implementations should handle:
    - Agent initialization and configuration
    - Conversation state management (message history or session ID)
    - Tool approval workflows
    - Response formatting
    """

    @abstractmethod
    async def send_message(self, message: str) -> PromptResponse:
        """Send a message to the agent and get a response.

        Args:
            message: The user's message

        Returns:
            PromptResponse containing either a message or tool approval requests
        """
        pass

    @abstractmethod
    async def process_tool_approvals(self, approvals: dict[str, ToolApprovalDecision]) -> PromptResponse:
        """Process user's tool approval decisions and continue agent execution.

        Args:
            approvals: Map of tool_call_id to approval decision

        Returns:
            PromptResponse with agent's next message or additional tool requests
        """
        pass
