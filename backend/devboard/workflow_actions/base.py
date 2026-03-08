"""Registry for workflow actions.

Workflow actions are reusable, named operations that can be triggered to send
predefined prompts to agent conversations, or perform structured actions.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.agent_execution import AgentExecutionService
from devboard.agents.events import ConversationEvent
from devboard.api.dependencies.factories import (
    create_agent_execution_service,
    create_agent_role_for_conversation,
)
from devboard.db.models import Conversation, ParentEntityType, Task
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.conversation_service import ConversationService
from devboard.services.integration_service import IntegrationService
from devboard.services.oauth_service import OAuthService
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_service import TaskService
from devboard.services.workspace_allocation_service import WorkspaceAllocationService


class TaskWorkflowAction(ABC):
    """A reusable workflow action that can be triggered in conversations.
    Can consist of a combination of traditional logic/actions as well as agent runs, both streaming
    events.

    Each concrete action is initialized with its specific service dependencies
    and implements the run() method to execute its logic.
    """

    # Subclasses must define these class attributes
    KEY: str  # Unique identifier (e.g., "task.create_implementation_plan")

    def __init__(
        self,
        task: Task,
        task_service: TaskService,
        task_git_service: TaskGitService,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
        document_repository: DocumentRepository,
        workspace_allocation_service: WorkspaceAllocationService,
        integration_service: IntegrationService,
        oauth_service: OAuthService | None = None,
    ):
        """Initialize the action with required services.

        Args:
            task: Task instance this workflow action operates on
            task_service: Service for task operations
            task_git_service: Service for task git operations
            conversation_repo: Repository for conversation database operations
            agent_config_service: Service for agent configuration
            document_repository: Repository for document database operations
            workspace_allocation_service: Service for workspace allocation
            integration_service: Service for external integrations (GitHub, etc.)
            oauth_service: Optional OAuthService for OAuth-authenticated MCP servers
        """
        self.task = task
        self.task_service = task_service
        self.task_git_service = task_git_service
        self.conversation_repo = conversation_repo
        self.agent_config_service = agent_config_service
        self.document_repository = document_repository
        self._oauth_service = oauth_service
        self.conversation_service = ConversationService(
            conversation_repo=conversation_repo,
            agent_config_service=agent_config_service,
        )
        self.workspace_allocation_service = workspace_allocation_service
        self.integration_service = integration_service

    async def _create_agent_execution_service(
        self,
        conversation: Conversation,
        additional_tools: list[Tool] | None = None,
    ) -> AgentExecutionService:
        """Create a new agent execution service for the given conversation with appropriate role.

        This factory method handles creating both the role and service instances
        for a conversation, ensuring the role matches the conversation's agent_role field.

        Args:
            conversation: The conversation instance to create a service for
            additional_tools: Optional list of additional tools to provide to the agent

        Returns:
            AgentExecutionService instance configured with the correct role
        """
        # Create role using the conversation's parent entity
        role = await create_agent_role_for_conversation(
            conversation=conversation,
            document_repo=self.document_repository,
            agent_config_service=self.agent_config_service,
            integration_service=self.integration_service,
            task_service=self.task_service,
            task_git_service=self.task_git_service,
        )

        # Create service with role and additional tools
        return create_agent_execution_service(
            conversation=conversation,
            role=role,
            conversation_repo=self.conversation_repo,
            agent_config_service=self.agent_config_service,
            additional_tools=additional_tools,
            oauth_service=self._oauth_service,
        )

    async def _stream_agent_response(
        self,
        conversation: Conversation,
        prompt: str,
        additional_tools: list[Tool] | None = None,
    ) -> AsyncIterator[ConversationEvent]:
        """Create agent service and stream response for a prompt in the task workspace.

        This helper encapsulates the common pattern of:
        1. Creating an agent conversation service
        2. Running the agent in the task's workspace
        3. Streaming events back to the caller

        Args:
            conversation: The conversation to use for the agent
            prompt: The prompt to send to the agent
            additional_tools: Optional list of additional tools for the agent

        Yields:
            ConversationEvent objects from the agent's response
        """
        agent_execution_service = await self._create_agent_execution_service(
            conversation,
            additional_tools=additional_tools,
        )

        agent_event_stream = self.workspace_allocation_service.run_task_agent_in_workspace(
            task=self.task,
            agent_stream=agent_execution_service.stream_events_for_message_or_approval(prompt),
        )

        async for event in agent_event_stream:
            yield event

    @classmethod
    @abstractmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task.

        Args:
            task: The task to check availability for

        Returns:
            True if the action is available, False otherwise
        """
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
        prompt_template: The prompt text to send to the agent
    """

    key: str
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
        task_git_service: TaskGitService,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
        document_repository: DocumentRepository,
        workspace_allocation_service: WorkspaceAllocationService,
        integration_service: IntegrationService,
        prompt_config: PromptTemplateActionConfig,
    ):
        """Initialize the action with required services and configuration.

        Args:
            task: Task instance this workflow action operates on
            task_service: Service for task operations
            task_git_service: Service for task git operations
            conversation_repo: Repository for conversation database operations
            agent_config_service: Service for agent configuration
            document_repository: Repository for document database operations
            workspace_allocation_service: Service for workspace allocation
            integration_service: Service for external integrations (GitHub, etc.)
            prompt_config: Configuration defining the action's key and prompt
        """
        super().__init__(
            task=task,
            task_service=task_service,
            task_git_service=task_git_service,
            conversation_repo=conversation_repo,
            agent_config_service=agent_config_service,
            document_repository=document_repository,
            workspace_allocation_service=workspace_allocation_service,
            integration_service=integration_service,
        )
        self.prompt_config = prompt_config

    @property
    def KEY(self) -> str:  # type: ignore[override]
        return self.prompt_config.key

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return True

    async def run(self) -> AsyncIterator[ConversationEvent]:
        """Execute the action by sending the prompt to the agent.

        Yields:
            ConversationEvent objects from the agent's response
        """
        # Get current active conversation and create service
        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, self.task.id)
        agent_execution_service = await self._create_agent_execution_service(conversation)

        # Stream agent prompt events
        async for event in agent_execution_service.stream_events_for_message_or_approval(
            self.prompt_config.prompt_template
        ):
            yield event
