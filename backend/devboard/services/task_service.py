"""Service for managing task lifecycle operations.

Handles task creation, phase transitions, and conversation lifecycle management.
Ensures proper agent configuration and conversation state throughout the task lifecycle.
"""

import re
from datetime import UTC, datetime
from typing import Any

import logfire

from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.custom_field import CustomFieldDefinition
from devboard.db.models.document import DocumentType
from devboard.db.models.enums import EntityType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories.custom_field import CustomFieldRepository
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.task import TaskRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.services.conversation_service import ConversationService
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_git_service import MergeOutcome, MergeResult, TaskGitService

RECENT_COMPLETED_TASKS_LIMIT = 5


class TaskTransitionError(Exception):
    """Base exception for task status transition errors."""


class TaskService:
    """Service for task lifecycle operations including creation and phase transitions."""

    def __init__(
        self,
        conversation_service: ConversationService,
        document_repo: DocumentRepository,
        task_repo: TaskRepository,
        custom_field_repo: CustomFieldRepository,
        system_event_emitter: SystemEventEmitter,
    ):
        self.conversation_service = conversation_service
        self.document_repo = document_repo
        self.task_repo = task_repo
        self.custom_field_repo = custom_field_repo
        self.system_event_emitter = system_event_emitter

    def _touch_updated_at(self, task: Task) -> None:
        task.updated_at = datetime.now(UTC)

    def _generate_branch_name(self, title: str) -> str:
        """Generate a branch name from a task title.

        Format: lowercase, alphanumeric + hyphens only, max 40 chars.
        """
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
        return slug

    async def create_task(
        self,
        project_id: int,
        title: str,
        base_branch: str,
        codebase_id: int,
        specification_content: str = "",
        branch_name: str | None = None,
        custom_fields: dict[str, Any] | None = None,
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
            specification_content: Initial content for the specification document (defaults to empty string)
            branch_name: Optional git branch name (auto-generated if not provided)
            custom_fields: Optional custom field values as a JSON-compatible dict

        Returns:
            Created Task instance with active conversation
        """
        # Auto-generate branch name from title if not provided
        if not branch_name:
            branch_name = self._generate_branch_name(title)
            logfire.info(f"Auto-generated branch name '{branch_name}' for new task")

        mandatory_fields = self.get_mandatory_custom_fields()
        if mandatory_fields:
            provided = custom_fields or {}
            missing = [
                f.name
                for f in mandatory_fields
                if f.name not in provided or provided[f.name] is None or provided[f.name] == ""
            ]
            if missing:
                raise ValueError(f"Missing required custom fields: {', '.join(missing)}")

        # Create documents
        specification_doc = self.document_repo.create(DocumentType.TASK_SPECIFICATION, specification_content)

        # Create task using repository (implementation plan will be created later when needed)
        task = self.task_repo.create(
            project_id=project_id,
            title=title,
            specification=specification_doc,
            implementation_plan=None,
            status=TaskStatus.PLANNING,
            codebase_id=codebase_id,
            branch_name=branch_name,
            base_branch=base_branch,
            custom_fields=custom_fields,
        )

        await TaskGitService.create_task_branch(task)

        # Create initial conversation with TASK_PLANNING role (handles both spec and planning)
        self.conversation_service.create_initial_conversation_for_parent_entity(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task.id,
            agent_role=AgentRoleType.TASK_PLANNING,
        )

        self.system_event_emitter.emit_task_created(task)

        return task

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
        self._touch_updated_at(task)
        return self.task_repo.update(task)

    async def delete_task(self, task: Task, delete_branch: bool = False) -> None:
        """Hard-delete a task and all related data.

        Performs a transactional deletion of:
        1. Conversations and their messages for the task
        2. The task itself
        3. Task-specific documents (specification and implementation plan)
        4. Optionally delete the git branch (if requested)

        Args:
            task: Task to delete
            delete_branch: If True, also delete the task's git branch (if it exists)
        """
        # 1. Delete conversations and messages for the task
        self.conversation_service.delete_conversations_for_parent(task)

        # These documents are exclusive to the task, so safe to delete
        if task.specification_id:
            self.document_repo.delete_by_id(task.specification_id)

        if task.implementation_plan_id:
            self.document_repo.delete_by_id(task.implementation_plan_id)

        # Explicitly delete structured plan (also cascade-deleted by ORM, belt-and-suspenders)
        self.task_repo.delete_implementation_plan_structured(task)

        # 2. Emit deleted event before hard delete (entity is still available for metadata)
        self.system_event_emitter.emit_task_deleted(task)

        # 3. Delete the task itself
        self.task_repo.delete(task)

        # 4. Delete git branch if requested
        if delete_branch:
            try:
                await TaskGitService.delete_task_branch(task, force=True)
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
        self._touch_updated_at(task)
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

    def _apply_complete_status(self, task: Task) -> Task:
        """Validate and apply COMPLETE status without emitting an event."""
        task.verify_status_transition(TaskStatus.COMPLETE)
        task.status = TaskStatus.COMPLETE
        self._touch_updated_at(task)
        self.task_repo.update(task)
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
        self._apply_complete_status(task)
        self.system_event_emitter.emit_task_completed(task, method="manual")
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

        merge_result = await TaskGitService.merge_task_feature_branch(task)

        # SUCCESS, SKIPPED (already merged), and STASH_CONFLICT (merge succeeded, WIP restore had conflicts) are all acceptable
        if merge_result.outcome not in (MergeOutcome.SUCCESS, MergeOutcome.SKIPPED, MergeOutcome.STASH_CONFLICT):
            raise ValueError(f"Merge failed ({merge_result.outcome.value}): {merge_result.message}")

        # Only create/update change_summary document after successful merge
        if not task.change_summary:
            doc = self.document_repo.create(DocumentType.CHANGE_SUMMARY, change_summary)
            task.change_summary_id = doc.id
            task.change_summary = doc
        else:
            self.document_repo.update_content(task.change_summary, change_summary)

        self._apply_complete_status(task)
        self.system_event_emitter.emit_task_completed(task, method="local_merge")
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
        git = GitRepoIntegration(task.codebase.local_path)
        try:
            await git.delete_branch(task.branch_name, force=True)
            logfire.info(f"Deleted local branch {task.branch_name} for task {task.id}")
        except Exception as e:
            logfire.warning(f"Failed to delete local branch {task.branch_name}: {e}")

        # Transition to COMPLETE
        self._apply_complete_status(task)
        self.system_event_emitter.emit_task_completed(task, method="pr_merge")
        self.task_repo.commit()

    def update_task(
        self,
        task: Task,
        title: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> Task:
        """Update task metadata fields with merge semantics for custom fields.

        Args:
            task: Task to update
            title: New title (unchanged if None)
            custom_fields: Dict to merge into existing custom_fields. Keys with None values are removed.

        Returns:
            Updated task instance
        """
        if title is not None:
            task.title = title

        if custom_fields is not None:
            merged = dict(task.custom_fields or {})
            for key, value in custom_fields.items():
                if value is None:
                    merged.pop(key, None)
                else:
                    merged[key] = value
            task.custom_fields = merged

        self._touch_updated_at(task)
        return self.task_repo.update(task)

    # Query methods (delegating to repository)

    def get_task_by_id(self, task_id: int, *, with_documents: bool = False) -> Task | None:
        """Get a task by its ID.

        Args:
            task_id: The task ID to search for
            with_documents: If True, eager load document relationships

        Returns:
            Task instance if found, None otherwise
        """
        return self.task_repo.get_by_id(task_id, with_documents=with_documents)

    def get_tasks_filtered(
        self,
        project_id: int,
        status_filter: list[TaskStatus] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        codebase_name: str | None = None,
        limit: int | None = None,
    ) -> list[Task]:
        return self.task_repo.get_tasks_filtered(
            project_id=project_id,
            status_filter=status_filter,
            created_after=created_after,
            created_before=created_before,
            codebase_name=codebase_name,
            limit=limit,
        )

    def get_custom_fields(self) -> list[CustomFieldDefinition]:
        """Get all custom field definitions."""
        return self.custom_field_repo.get_all(entity_type=EntityType.TASK)

    def get_mandatory_custom_fields(self) -> list[CustomFieldDefinition]:
        """Get all mandatory custom field definitions."""
        return self.custom_field_repo.get_mandatory_fields(entity_type=EntityType.TASK)

    def get_project_task_summaries(
        self,
        project_id: int,
        recent_completed_limit: int = RECENT_COMPLETED_TASKS_LIMIT,
    ) -> tuple[list[Task], list[Task]]:
        """Get active and recently completed tasks for project context.

        Returns:
            Tuple of (active_tasks, recent_completed_tasks), both sorted by updated_at descending.
        """
        all_tasks = self.task_repo.get_list(project_id=project_id)
        active_statuses = {TaskStatus.PLANNING, TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN}
        active = sorted(
            [t for t in all_tasks if t.status in active_statuses],
            key=lambda t: t.updated_at,
            reverse=True,
        )
        completed = sorted(
            [t for t in all_tasks if t.status == TaskStatus.COMPLETE],
            key=lambda t: t.updated_at,
            reverse=True,
        )[:recent_completed_limit]
        return active, completed
