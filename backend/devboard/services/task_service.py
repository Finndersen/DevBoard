"""Service for managing task lifecycle operations.

Handles task creation, phase transitions, and conversation lifecycle management.
Ensures proper agent configuration and conversation state throughout the task lifecycle.
"""

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.types import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.task import TaskRepository


class TaskService:
    """Service for task lifecycle operations including creation and phase transitions."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        document_repo: DocumentRepository,
        task_repo: TaskRepository,
        agent_config_service: AgentConfigService,
    ):
        """Initialize service.

        Args:
            conversation_repo: Repository for conversation operations
            document_repo: Repository for document operations
            task_repo: Repository for task operations
            agent_config_service: Service for agent configuration
        """
        self.conversation_repo = conversation_repo
        self.document_repo = document_repo
        self.task_repo = task_repo
        self.agent_config_service = agent_config_service

    def create_task(
        self,
        project_id: int,
        title: str,
        status: TaskStatus = TaskStatus.DEFINING,
        codebase_id: int | None = None,
        remote_task_id: str | None = None,
        specification_content: str = "",
    ) -> Task:
        """Create a new task with initial conversation.

        Creates the task entity, required documents, and an initial active conversation
        configured with the appropriate agent role, engine, and model based on the
        task's initial status.

        Args:
            project_id: ID of the project this task belongs to
            title: Task title
            status: Initial task status (defaults to DEFINING)
            codebase_id: Optional codebase ID
            remote_task_id: Optional remote task identifier (e.g., Jira issue key)
            specification_content: Initial content for the specification document (defaults to empty string)

        Returns:
            Created Task instance with active conversation
        """
        # Create documents
        specification_doc = self.document_repo.create(DocumentType.TASK_SPECIFICATION, specification_content)

        # Create task using repository (implementation plan will be created later when needed)
        task = self.task_repo.create(
            project_id=project_id,
            title=title,
            specification=specification_doc,
            implementation_plan=None,
            status=status,
            codebase_id=codebase_id,
            remote_task_id=remote_task_id,
        )

        # Determine agent role from status
        agent_role = self._get_agent_role_for_status(status)

        # Get effective config for role
        config = self.agent_config_service.get_effective_config(agent_role)

        # Create initial conversation (external_session_id will be set later if needed)
        self.conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task.id,
            agent_role=agent_role,
            engine=config.engine,
            model_id=config.model_id,
            external_session_id=None,
            is_active=True,
        )

        return task

    def transition_to_planning(self, task: Task) -> Task:
        """Transition task from DEFINING to PLANNING status.

        Creates implementation_plan document if needed and updates task status.

        Args:
            task: Task to transition

        Returns:
            Updated task instance

        Raises:
            ValueError: If task is not in DEFINING status or transition validation fails
        """
        # Verify current status
        if task.status != TaskStatus.DEFINING:
            raise ValueError(
                f"Cannot transition to PLANNING: task {task.id} must be in DEFINING status, "
                f"currently in {task.status.value}"
            )

        # Validate transition
        can_transition, error_msg = task.can_transition_to_phase(TaskStatus.PLANNING)
        if not can_transition:
            raise ValueError(f"Cannot transition task {task.id} to PLANNING: {error_msg}")

        # Create implementation_plan document if needed
        if not task.implementation_plan:
            implementation_plan_doc = self.document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
            task.implementation_plan_id = implementation_plan_doc.id
            task.implementation_plan = implementation_plan_doc

        # Update task status
        task.status = TaskStatus.PLANNING
        return self.task_repo.update(task)

    def transition_to_implementing(self, task: Task) -> Task:
        """Transition task from PLANNING to IMPLEMENTING status.

        Args:
            task: Task to transition

        Returns:
            Updated task instance

        Raises:
            ValueError: If task is not in PLANNING status or transition validation fails
        """
        # Verify current status
        if task.status != TaskStatus.PLANNING:
            raise ValueError(
                f"Cannot transition to IMPLEMENTING: task {task.id} must be in PLANNING status, "
                f"currently in {task.status.value}"
            )

        # Validate transition
        can_transition, error_msg = task.can_transition_to_phase(TaskStatus.IMPLEMENTING)
        if not can_transition:
            raise ValueError(f"Cannot transition task {task.id} to IMPLEMENTING: {error_msg}")

        # Update task status
        task.status = TaskStatus.IMPLEMENTING
        return self.task_repo.update(task)

    @staticmethod
    def _get_agent_role_for_status(status: TaskStatus) -> AgentRoleType:
        """Map task status to agent role.

        Args:
            status: Task status

        Returns:
            Corresponding AgentRole
        """
        mapping = {
            TaskStatus.DEFINING: AgentRoleType.TASK_SPECIFICATION,
            TaskStatus.PLANNING: AgentRoleType.TASK_PLANNING,
            TaskStatus.IMPLEMENTING: AgentRoleType.TASK_IMPLEMENTATION,
            TaskStatus.REVIEWING: AgentRoleType.TASK_IMPLEMENTATION,  # Same agent for review
        }
        return mapping.get(status, AgentRoleType.TASK_SPECIFICATION)
