"""Service for managing task lifecycle operations.

Handles task creation, phase transitions, and conversation lifecycle management.
Ensures proper agent configuration and conversation state throughout the task lifecycle.
"""

import re

import logfire

from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.task import TaskRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.services.conversation_service import ConversationService
from devboard.services.task_git_service import MergeOutcome, MergeResult, TaskGitService


class TaskTransitionError(Exception):
    """Base exception for task status transition errors."""


class TaskService:
    """Service for task lifecycle operations including creation and phase transitions."""

    def __init__(
        self,
        conversation_service: ConversationService,
        document_repo: DocumentRepository,
        task_repo: TaskRepository,
        worktree_slot_repo: WorktreeSlotRepository,
    ):
        """Initialize service.

        Args:
            conversation_service: Service for conversation operations
            document_repo: Repository for document operations
            task_repo: Repository for task operations
            worktree_slot_repo: Repository for worktree slot operations
        """
        self.conversation_service = conversation_service
        self.document_repo = document_repo
        self.task_repo = task_repo
        self.worktree_slot_repo = worktree_slot_repo

    def _generate_branch_name(self, title: str) -> str:
        """Generate a branch name from a task title.

        Format: lowercase, alphanumeric + hyphens only, max 40 chars.
        """
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
        return slug

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

        If no branch name is provided, a branch name will be auto-generated from the title.

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
        # Auto-generate branch name from title if not provided
        if not branch_name:
            branch_name = self._generate_branch_name(title)
            logfire.info(f"Auto-generated branch name '{branch_name}' for new task")

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
            InvalidStatusTransitionError: If transition is not valid
        """
        task.verify_status_transition(TaskStatus.PLANNING)

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
            InvalidStatusTransitionError: If transition is not valid
        """
        task.verify_status_transition(TaskStatus.IMPLEMENTING)

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
        self.conversation_service.delete_conversations_for_parent(task)

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

    def transition_to_pr_open(self, task: Task, pr_number: int) -> Task:
        """Transition task from IMPLEMENTING to PR_OPEN status.

        This method:
        1. Validates the transition is allowed
        2. Updates task status and PR number
        3. Creates new conversation with TASK_PR_REVIEW role
        4. Commits all changes atomically

        Args:
            task: Task to transition
            pr_number: GitHub PR number to associate with task

        Returns:
            Updated task instance

        Raises:
            InvalidStatusTransitionError: If transition is not valid
        """
        task.verify_status_transition(TaskStatus.PR_OPEN)

        # Update task status and PR number
        task.github_pr_number = pr_number
        task.status = TaskStatus.PR_OPEN
        self.task_repo.update(task)

        # Create new conversation with TASK_PR_REVIEW role for PR feedback handling
        self.conversation_service.replace_active_conversation(
            entity_type=ParentEntityType.TASK,
            entity_id=task.id,
            new_agent_role=AgentRoleType.TASK_PR_REVIEW,
        )

        # Commit all changes atomically
        self.task_repo.commit()

        return task

    def transition_to_complete(self, task: Task) -> Task:
        """Transition task from IMPLEMENTING or PR_OPEN to COMPLETE status.

        Note: change_summary document should be created by the workflow action
        using the set_change_summary tool before calling this method.

        Args:
            task: Task to transition

        Returns:
            Updated task instance

        Raises:
            InvalidStatusTransitionError: If transition is not valid
        """
        task.verify_status_transition(TaskStatus.COMPLETE)

        # Update task status
        task.status = TaskStatus.COMPLETE
        self.task_repo.update(task)
        return task

    async def complete_task_with_local_merge(self, task: Task, change_summary: str) -> MergeResult:
        """Complete a task by merging its feature branch locally.

        This method handles the complete merge workflow for local/solo development:
        1. Creates the change_summary document for the task
        2. Merges feature branch into base branch using codebase merge strategy
        3. Deletes the feature branch
        4. Transitions task to COMPLETE status

        Args:
            task: Task to complete
            change_summary: Markdown content summarizing the changes made

        Returns:
            MergeResult with outcome and relevant details

        Raises:
            ValueError: If task has no branch configured, merge strategy is invalid,
                or merge fails (conflict/error)
            InvalidStatusTransitionError: If task cannot transition to COMPLETE
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch configured")

        # Create change_summary document
        if not task.change_summary:
            doc = self.document_repo.create(DocumentType.CHANGE_SUMMARY, change_summary)
            task.change_summary_id = doc.id
            task.change_summary = doc
        else:
            self.document_repo.update_content(task.change_summary, change_summary)

        task_git_service = TaskGitService(task_repo=self.task_repo, worktree_slot_repo=self.worktree_slot_repo)
        merge_result = await task_git_service.merge_task_feature_branch(task)

        # SUCCESS and SKIPPED (already merged) are both acceptable outcomes
        if merge_result.outcome not in (MergeOutcome.SUCCESS, MergeOutcome.SKIPPED):
            raise ValueError(f"Merge failed ({merge_result.outcome.value}): {merge_result.message}")

        self.transition_to_complete(task)
        self.task_repo.commit()
        return merge_result

    async def complete_pr_task(self, task: Task, change_summary: str) -> None:
        """Complete a task that has an open/merged PR.

        This method handles post-merge cleanup and task completion:
        1. Creates the change_summary document
        2. Deletes local feature branch
        3. Transitions task to COMPLETE

        Note: PR merging should be handled by the caller before calling this method.

        Args:
            task: Task with PR to complete
            change_summary: Markdown content summarizing the changes made

        Raises:
            ValueError: If task has no PR reference
            InvalidStatusTransitionError: If task cannot transition to COMPLETE
        """
        if not task.github_pr_number:
            raise ValueError(f"Task {task.id} has no PR configured")

        # Create change_summary document
        if not task.change_summary:
            doc = self.document_repo.create(DocumentType.CHANGE_SUMMARY, change_summary)
            task.change_summary_id = doc.id
            task.change_summary = doc
        else:
            self.document_repo.update_content(task.change_summary, change_summary)

        # Delete local feature branch
        if task.branch_name:
            git = GitRepoIntegration(task.codebase.local_path)
            try:
                await git.delete_branch(task.branch_name, force=True)
                logfire.info(f"Deleted local branch {task.branch_name} for task {task.id}")
            except Exception as e:
                logfire.warning(f"Failed to delete local branch {task.branch_name}: {e}")

        # Transition to COMPLETE
        self.transition_to_complete(task)
        self.task_repo.commit()
