"""Registry for workflow actions.

Workflow actions are reusable, named operations that can be triggered to perform
task state transitions and/or return a prompt to start an agent conversation.
"""

from abc import ABC, abstractmethod

from devboard.agents.agent_config_service import AgentConfigService
from devboard.db.models import Task
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.conversation_service import ConversationService
from devboard.services.integration_service import IntegrationService
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_service import TaskService


class TaskWorkflowAction(ABC):
    """A reusable workflow action that can be triggered for a task.

    Actions perform optional procedural steps (state transitions, DB changes) and
    return either a prompt string to start an agent run, or None if no agent is needed.
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
        integration_service: IntegrationService,
    ):
        self.task = task
        self.task_service = task_service
        self.task_git_service = task_git_service
        self.conversation_repo = conversation_repo
        self.agent_config_service = agent_config_service
        self.document_repository = document_repository
        self.conversation_service = ConversationService(
            conversation_repo=conversation_repo,
            agent_config_service=agent_config_service,
        )
        self.integration_service = integration_service

    @classmethod
    @abstractmethod
    def is_available(cls, task: Task) -> bool:
        """Check if this action is available for the given task."""
        pass

    @abstractmethod
    async def run(self) -> str | None:
        """Execute the action's procedural steps and return an optional agent prompt.

        Returns:
            A prompt string to start an agent run on the task's active conversation,
            or None if no agent interaction is needed.
        """
        pass
