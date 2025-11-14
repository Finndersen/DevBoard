"""Registry for workflow actions.

Workflow actions are reusable, named operations that can be triggered to send
predefined prompts to agent conversations, or perform structured actions.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.events import ConversationEvent
from devboard.db.models import Task
from devboard.db.repositories import ConversationRepository
from devboard.services.conversation_service import ConversationService
from devboard.services.task_service import TaskService


class TaskWorkflowAction(ABC):
    """A reusable workflow action that can be triggered in conversations.
    Can consist of a combination of traditional logic/actions as well as agent runs, both streaming
    events.

    Each concrete action is initialized with its specific service dependencies
    and implements the run() method to execute its logic.
    """

    def __init__(
        self,
        task: Task,
        agent_conversation_service: BaseAgentConversationService,
        task_service: TaskService,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
    ):
        """Initialize the action with required services.

        Args:
            task: Task instance this workflow action operates on
            agent_conversation_service: Service for agent conversation operations
            task_service: Service for task operations
            conversation_repo: Repository for conversation database operations
            agent_config_service: Service for agent configuration
        """
        self.task = task
        self.agent_conversation_service = agent_conversation_service
        self.task_service = task_service
        self.conversation_repo = conversation_repo
        self.agent_config_service = agent_config_service
        self.conversation_service = ConversationService(
            conversation_repo=conversation_repo,
            agent_config_service=agent_config_service,
        )

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
        if False:
            yield  # type: ignore[unreachable]  # Required for async generator type inference


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


class PromptTemplateAction(TaskWorkflowAction):
    """Simple workflow action that sends a predefined prompt to the agent.

    This is a convenience subclass for actions that only need to send a prompt
    without additional structured logic. Created from a PromptTemplateActionConfig.
    """

    def __init__(
        self,
        task: Task,
        agent_conversation_service: BaseAgentConversationService,
        task_service: TaskService,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
        prompt_config: PromptTemplateActionConfig,
    ):
        """Initialize the action with required services and configuration.

        Args:
            task: Task instance this workflow action operates on
            agent_conversation_service: Service for agent conversation operations
            task_service: Service for task operations
            conversation_repo: Repository for conversation database operations
            agent_config_service: Service for agent configuration
            prompt_config: Configuration defining the action's key, description, and prompt
        """
        super().__init__(
            task=task,
            agent_conversation_service=agent_conversation_service,
            task_service=task_service,
            conversation_repo=conversation_repo,
            agent_config_service=agent_config_service,
        )
        self.prompt_config = prompt_config

    @property
    def key(self) -> str:
        return self.prompt_config.key

    @property
    def description(self) -> str:
        return self.prompt_config.description

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action by sending the prompt to the agent.

        Yields:
            ConversationEvent objects from the agent's response
        """
        async for event in self.agent_conversation_service.stream_events_for_message_or_approval(
            self.prompt_config.prompt_template
        ):
            yield event
