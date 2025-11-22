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
from devboard.api.dependencies.factories import (
    create_agent_conversation_service,
    create_agent_role_for_conversation,
)
from devboard.db.models import Conversation, ParentEntityType, Task
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.conversation_service import ConversationService
from devboard.services.task_service import TaskService
from devboard.services.workspace_allocation_service import WorkspaceAllocationService


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
        task_service: TaskService,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
        document_repository: DocumentRepository,
        workspace_allocation_service: WorkspaceAllocationService,
    ):
        """Initialize the action with required services.

        Args:
            task: Task instance this workflow action operates on
            task_service: Service for task operations
            conversation_repo: Repository for conversation database operations
            agent_config_service: Service for agent configuration
            document_repository: Repository for document database operations
            workspace_allocation_service: Service for workspace allocation
        """
        self.task = task
        self.task_service = task_service
        self.conversation_repo = conversation_repo
        self.agent_config_service = agent_config_service
        self.document_repository = document_repository
        self.conversation_service = ConversationService(
            conversation_repo=conversation_repo,
            agent_config_service=agent_config_service,
        )
        self.workspace_allocation_service = workspace_allocation_service

    def _create_agent_conversation_service(self, conversation: Conversation) -> BaseAgentConversationService:
        """Create a new agent service for the given conversation with appropriate role.

        This factory method handles creating both the role and service instances
        for a conversation, ensuring the role matches the conversation's agent_role field.

        Args:
            conversation: The conversation instance to create a service for

        Returns:
            BaseAgentConversationService instance configured with the correct role
        """

        # Create role using the conversation's parent entity
        role = create_agent_role_for_conversation(
            conversation=conversation,
            document_repo=self.document_repository,
            agent_config_service=self.agent_config_service,
        )

        # Create service using the role
        return create_agent_conversation_service(
            conversation=conversation,
            role=role,
            conversation_repo=self.conversation_repo,
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
        task_service: TaskService,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
        document_repository: DocumentRepository,
        prompt_config: PromptTemplateActionConfig,
    ):
        """Initialize the action with required services and configuration.

        Args:
            task: Task instance this workflow action operates on
            task_service: Service for task operations
            conversation_repo: Repository for conversation database operations
            agent_config_service: Service for agent configuration
            document_repository: Repository for document database operations
            prompt_config: Configuration defining the action's key, description, and prompt
        """
        super().__init__(
            task=task,
            task_service=task_service,
            conversation_repo=conversation_repo,
            agent_config_service=agent_config_service,
            document_repository=document_repository,
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
        # Get current active conversation and create service
        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, self.task.id)
        agent_conversation_service = self._create_agent_conversation_service(conversation)

        # Stream agent prompt events
        async for event in agent_conversation_service.stream_events_for_message_or_approval(
            self.prompt_config.prompt_template
        ):
            yield event
