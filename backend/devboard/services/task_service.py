"""Service for managing task lifecycle operations.

Handles task creation, phase transitions, and conversation lifecycle management.
Ensures proper agent configuration and conversation state throughout the task lifecycle.
"""

import logfire

from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.task import TaskRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.services.conversation_service import ConversationService
from devboard.services.task_git_service import TaskGitService


class TaskTransitionError(Exception):
    """Base exception for task status transition errors."""


class InvalidTaskStatusError(TaskTransitionError):
    """Raised when a task is in an invalid status for the requested transition."""


class TaskTransitionValidationError(TaskTransitionError):
    """Raised when a task transition fails validation (e.g., missing prerequisites)."""


class TaskService:
    """Service for task lifecycle operations including creation and phase transitions."""

    def __init__(
        self,
        conversation_service: ConversationService,
        document_repo: DocumentRepository,
        task_repo: TaskRepository,
        conversation_repo: ConversationRepository,
        worktree_slot_repo: WorktreeSlotRepository,
    ):
        """Initialize service.

        Args:
            conversation_service: Service for conversation operations
            document_repo: Repository for document operations
            task_repo: Repository for task operations
            conversation_repo: Repository for conversation operations
            worktree_slot_repo: Repository for worktree slot operations
        """
        self.conversation_service = conversation_service
        self.document_repo = document_repo
        self.task_repo = task_repo
        self.conversation_repo = conversation_repo
        self.worktree_slot_repo = worktree_slot_repo

    def create_task(
        self,
        project_id: int,
        title: str,
        base_branch: str,
        codebase_id: int,
        remote_task_id: str | None = None,
        specification_content: str = "",
        branch_name: str | None = None,
    ) -> Task:
        """Create a new task with initial conversation.

        Creates the task entity, required documents, and an initial active conversation
        configured with the appropriate agent role, engine, and model based on the
        task's initial status.

        If no branch name is provided, a branch name will be auto-generated and the
        branch will be created in git (if it doesn't already exist).

        Args:
            project_id: ID of the project this task belongs to
            title: Task title
            base_branch: Base branch for git operations
            codebase_id: Codebase ID
            remote_task_id: Optional remote task identifier (e.g., Jira issue key)
            specification_content: Initial content for the specification document (defaults to empty string)
            branch_name: Optional git branch name (auto-generated if not provided)

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
            branch_name=branch_name,
            base_branch=base_branch,
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
            InvalidTaskStatusError: If task is not in DEFINING status
            TaskTransitionValidationError: If transition validation fails
        """
        # Verify current status
        if task.status != TaskStatus.DEFINING:
            raise InvalidTaskStatusError(
                f"Cannot transition to PLANNING: task {task.id} must be in DEFINING status, "
                f"currently in {task.status.value}"
            )

        # Validate transition
        can_transition, error_msg = task.can_transition_to_phase(TaskStatus.PLANNING)
        if not can_transition:
            raise TaskTransitionValidationError(f"Cannot transition task {task.id} to PLANNING: {error_msg}")

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
            InvalidTaskStatusError: If task is not in PLANNING status
            TaskTransitionValidationError: If transition validation fails
        """
        # Verify current status
        if task.status != TaskStatus.PLANNING:
            raise InvalidTaskStatusError(
                f"Cannot transition to IMPLEMENTING: task {task.id} must be in PLANNING status, "
                f"currently in {task.status.value}"
            )

        # Validate transition
        can_transition, error_msg = task.can_transition_to_phase(TaskStatus.IMPLEMENTING)
        if not can_transition:
            raise TaskTransitionValidationError(f"Cannot transition task {task.id} to IMPLEMENTING: {error_msg}")

        # Update task status
        task.status = TaskStatus.IMPLEMENTING
        return self.task_repo.update(task)

    async def delete_task(self, task: Task, delete_branch: bool = False) -> None:
        """Hard-delete a task and all related data.

        Performs a transactional deletion of:
        1. Task-context resource associations
        2. Conversations and their messages for the task
        3. The task itself
        4. Task-specific documents (specification and implementation plan)
        5. Optionally delete the git branch (if requested)

        Args:
            task: Task to delete
            delete_branch: If True, also delete the task's git branch (if it exists)
        """
        # 1. Delete task-context resource associations (required - no CASCADE on FK)
        self.task_repo.delete_task_context_resources(task)

        # 2. Delete conversations and messages for the task
        self.conversation_repo.delete_by_parent(ParentEntityType.TASK, task.id)

        # These documents are exclusive to the task, so safe to delete
        if task.specification_id:
            self.document_repo.delete_by_id(task.specification_id)

        if task.implementation_plan_id:
            self.document_repo.delete_by_id(task.implementation_plan_id)

        # 3. Delete the task itself
        self.task_repo.delete(task)

        # 4. Delete git branch if requested
        task_git_service = TaskGitService(task_repo=self.task_repo, worktree_slot_repo=self.worktree_slot_repo)
        if delete_branch and task.branch_name:
            try:
                await task_git_service.delete_task_branch(task, force=True)
            except Exception as e:
                # Log error but don't fail task deletion
                logfire.warning(f"Failed to delete branch {task.branch_name} for task {task.id}: {e}")
