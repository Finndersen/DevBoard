"""Registry for workflow actions.

Workflow actions are reusable, named operations that can be triggered to send
predefined prompts to agent conversations, or perform structured actions.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.events import ConversationEvent


class WorkflowAction(ABC):
    """A reusable workflow action that can be triggered in conversations.
    Can consist of a combination of traditional logic/actions as well as agent runs, both streaming
    events.

    Each concrete action is initialized with its specific service dependencies
    and implements the run() method to execute its logic.
    """

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique identifier for the action (e.g., "task.create_implementation_plan")."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for UI display."""
        pass

    @abstractmethod
    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action and yield conversation events.

        Yields:
            ConversationEvent objects representing messages, tool calls, or system events
        """
        pass


@dataclass(frozen=True)
class PromptTemplateActionConfig:
    """Configuration for a simple prompt template action.

    This defines a reusable prompt action that sends a predefined prompt
    to the agent. Supports both built-in and user-defined actions.

    Attributes:
        key: Unique identifier for the action (e.g., "task.create_implementation_plan")
        description: Human-readable description for UI display
        prompt_template: The prompt text to send to the agent
    """

    key: str
    description: str
    prompt_template: str


class PromptTemplateAction(WorkflowAction):
    """Simple workflow action that sends a predefined prompt to the agent.

    This is a convenience subclass for actions that only need to send a prompt
    without additional structured logic. Created from a PromptTemplateActionConfig.
    """

    def __init__(
        self,
        conversation_service: BaseAgentConversationService,
        config: PromptTemplateActionConfig,
    ):
        """Initialize the action with required services and configuration.

        Args:
            conversation_service: Service for agent conversation operations
            config: Configuration defining the action's key, description, and prompt
        """
        self.conversation_service = conversation_service
        self.config = config

    @property
    def key(self) -> str:
        return self.config.key

    @property
    def description(self) -> str:
        return self.config.description

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action by sending the prompt to the agent.

        Yields:
            ConversationEvent objects from the agent's response
        """
        async for event in self.conversation_service.stream_events_for_message_or_approval(self.config.prompt_template):
            yield event
