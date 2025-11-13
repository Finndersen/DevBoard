"""Service for managing and executing workflow actions."""

from collections.abc import AsyncIterator

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.events import ConversationEvent
from devboard.agents.prompt_actions import WORKFLOW_ACTION_DEFINITIONS, WorkflowAction


class PromptActionNotFoundError(Exception):
    """Raised when a requested workflow action key does not exist."""

    pass


class PromptActionService:
    """Service for managing and executing workflow actions.

    Workflow actions are reusable, named operations that can send prompts
    to agent conversations or perform structured actions with system events.
    This service handles action lookup, instantiation, and execution.
    """

    def __init__(self, conversation_service: BaseAgentConversationService):
        """Initialize the service.

        Args:
            conversation_service: Service for agent conversation operations
        """
        self.conversation_service = conversation_service

    def get_action(self, action_key: str) -> WorkflowAction | None:
        """Look up and instantiate a workflow action by key.

        Args:
            action_key: The unique identifier for the action

        Returns:
            WorkflowAction instance if found, None otherwise
        """
        # Find and instantiate the action by key
        for action_class, init_kwargs in WORKFLOW_ACTION_DEFINITIONS:
            # For PromptTemplateAction, check the config key
            if "config" in init_kwargs and init_kwargs["config"].key == action_key:
                # Instantiate with conversation service and the defined kwargs
                return action_class(self.conversation_service, **init_kwargs)
            # For other action types, check if action_key is in init_kwargs
            elif init_kwargs.get("action_key") == action_key:
                return action_class(self.conversation_service, **init_kwargs)

        return None

    async def stream_action(self, action_key: str) -> AsyncIterator[ConversationEvent]:
        """Stream events from executing a workflow action.

        Args:
            action_key: The unique identifier for the action to execute

        Yields:
            ConversationEvent objects as they are generated from executing the action

        Raises:
            PromptActionNotFoundError: If the action_key does not exist
        """
        # Look up and instantiate the action
        action = self.get_action(action_key)
        if action is None:
            raise PromptActionNotFoundError(f"Workflow action '{action_key}' not found")

        # Stream events from the action's run() method
        async for event in action.run():
            yield event
