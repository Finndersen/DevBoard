"""Service for managing task lifecycle operations.

Handles task creation, phase transitions, and conversation lifecycle management.
Ensures proper agent configuration and conversation state throughout the task lifecycle.
"""

from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.task import TaskRepository
from devboard.services.conversation_service import ConversationService


class TaskService:
    """Service for task lifecycle operations including creation and phase transitions."""

    def __init__(
        self,
        conversation_service: ConversationService,
        document_repo: DocumentRepository,
        task_repo: TaskRepository,
    ):
        """Initialize service.

        Args:
            conversation_service: Service for conversation operations
            document_repo: Repository for document operations
            task_repo: Repository for task operations
        """
        self.conversation_service = conversation_service
        self.document_repo = document_repo
        self.task_repo = task_repo

    def create_task(
        self,
        project_id: int,
        title: str,
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
            status=TaskStatus.DEFINING,
            codebase_id=codebase_id,
            remote_task_id=remote_task_id,
        )

        # Create initial conversation
        self.conversation_service.create_initial_conversation_for_parent_entity(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
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
