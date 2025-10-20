"""Service for managing and executing prompt actions."""

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.prompt_actions import PromptAction, prompt_action_registry
from devboard.api.schemas.agent_conversation import ConversationEvent


class PromptActionNotFoundError(Exception):
    """Raised when a requested prompt action key does not exist."""

    pass


class PromptActionService:
    """Service for managing and executing prompt actions.

    Prompt actions are reusable, named operations that send predefined prompts
    to agent conversations. This service handles action lookup and execution.
    """

    def __init__(self, conversation_service: BaseAgentConversationService):
        """Initialize the service.

        Args:
            conversation_service: Service for agent conversation operations
        """
        self.conversation_service = conversation_service

    def get_action(self, action_key: str) -> PromptAction | None:
        """Look up a prompt action by key.

        Args:
            action_key: The unique identifier for the action

        Returns:
            PromptAction if found, None otherwise
        """
        return prompt_action_registry.get(action_key)

    async def execute_action(self, action_key: str) -> list[ConversationEvent]:
        """Execute a prompt action by sending its prompt to a conversation.

        Args:
            action_key: The unique identifier for the action to execute

        Returns:
            List of ConversationEvent objects from processing the prompt action

        Raises:
            PromptActionNotFoundError: If the action_key does not exist
        """
        # Look up the action
        action = self.get_action(action_key)
        if action is None:
            raise PromptActionNotFoundError(f"Prompt action '{action_key}' not found")

        # Send the prompt as a user message
        result = await self.conversation_service.send_message(message=action.prompt_template)

        return result
