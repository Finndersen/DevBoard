"""Service for task git operations.

Handles git branch operations for tasks including branch creation,
status checking, merging, and deletion.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

import logfire

from devboard.db.models.task import Task
from devboard.db.repositories.task import TaskRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.types import CommitDiff, GitLogEntry, StructuredDiff


class TaskDiffView(StrEnum):
    """View types for task diff endpoint."""

    ALL = "all"  # Combined diff from merge base to working directory
    UNCOMMITTED = "uncommitted"  # Only uncommitted changes
    # Individual commit hashes are also supported but not in enum


@dataclass
class TaskDiffResult:
    """Structured diff result for a task including commits and uncommitted changes."""

    commits: list[CommitDiff]
    uncommitted_changes: StructuredDiff | None
    total_additions: int
    total_deletions: int


class TaskGitService:
    """Service for task git operations."""

    def __init__(self, task_repo: TaskRepository, worktree_slot_repo: WorktreeSlotRepository):
        """Initialize service.

        Args:
            task_repo: Task repository for updating task.branch_name
            worktree_slot_repo: Worktree slot repository for finding task worktree slots
        """
        self.task_repo = task_repo
        self.worktree_slot_repo = worktree_slot_repo

    async def ensure_task_branch(self, task: Task) -> str:
        """Ensure task has a branch, creating it if necessary.

        This method is called at the start of the implementation phase to ensure
        the task has a git branch to work on. If branch_name is not set, it will
        auto-generate one. If the branch doesn't exist in git, it will be created.

        Args:
            task: Task instance

        Returns:
            The branch name (either existing or newly generated)

        Raises:
            ValueError: If task configuration is invalid
        """
        # Generate branch name if not set
        if not task.branch_name:
            branch_name = self._generate_branch_name(task)
            task.branch_name = branch_name

            # Update task in database
            self.task_repo.update(task)
            logfire.info(f"Auto-generated branch name {branch_name} for task {task.id}")
        else:
            branch_name = task.branch_name

        # Create branch if it doesn't exist
        git = GitRepoIntegration(task.codebase.local_path)
        if not await git.branch_exists(branch_name):
            await git.create_branch(branch_name, task.base_branch)
            logfire.info(f"Created branch {branch_name} from {task.base_branch} for task {task.id}")
        else:
            logfire.info(f"Branch {branch_name} already exists for task {task.id}")

        return branch_name

    def _generate_branch_name(self, task: Task) -> str:
        """Generate a branch name for a task.

        Format: devboard/task-{id}-{slug}
        """
        # Create slug from title (lowercase, alphanumeric + hyphens only, max 40 chars)
        slug = re.sub(r"[^a-z0-9]+", "-", task.title.lower()).strip("-")[:40]
        # TODO: Make this a configurable template on a per-codebase basis?
        # return f"devboard/task-{task.id}-{slug}"
        return slug

    async def get_task_commit_metadata(self, task: Task) -> list[GitLogEntry]:
        """Get lightweight commit metadata for a task branch.

        Returns commit metadata (hash, author, date, message) without file diffs.
        Used for populating UI dropdowns. Always runs against main codebase path.

        Args:
            task: Task instance

        Returns:
            List of GitLogEntry objects for commits in the task branch

        Raises:
            ValueError: If task has no branch configured
        """
        if not task.branch_name:
            return []

        git = GitRepoIntegration(task.codebase.local_path)

        # Get merge base to find where task branch diverged from base
        merge_base = await git.get_merge_base(task.base_branch, task.branch_name)

        # Get commits in the task branch since merge base
        commits = await git.get_commits_in_range(merge_base, task.branch_name)

        return commits

    async def get_task_git_status(self, task: Task) -> dict:
        """Get git status for a task's branch.

        Args:
            task: Task instance

        Returns:
            Dictionary with git status information:
            - branch_name: str | None
            - branch_exists: bool
            - base_branch: str
            - commits_ahead: int
            - commits_behind: int
            - can_merge: bool
            - has_conflicts: bool

        Raises:
            ValueError: If task configuration is invalid
        """
        if not task.branch_name:
            return {
                "branch_name": None,
                "branch_exists": False,
                "base_branch": task.base_branch,
                "commits_ahead": 0,
                "commits_behind": 0,
                "can_merge": False,
                "has_conflicts": False,
            }

        git = GitRepoIntegration(task.codebase.local_path)

        # Check if branch exists
        branch_exists = await git.branch_exists(task.branch_name)

        if not branch_exists:
            return {
                "branch_name": task.branch_name,
                "branch_exists": False,
                "base_branch": task.base_branch,
                "commits_ahead": 0,
                "commits_behind": 0,
                "can_merge": False,
                "has_conflicts": False,
            }

        # Get branch comparison
        comparison = await git.get_branch_comparison(task.branch_name, task.base_branch)

        return {
            "branch_name": task.branch_name,
            "branch_exists": True,
            "base_branch": task.base_branch,
            "commits_ahead": comparison.ahead,
            "commits_behind": comparison.behind,
            "can_merge": comparison.can_merge,
            "has_conflicts": comparison.has_conflicts,
        }

    async def merge_task_branch(
        self,
        task: Task,
        target_branch: str | None = None,
        delete_branch: bool = False,
    ) -> str:
        """Merge a task's branch into its base branch.

        Args:
            task: Task instance
            target_branch: Target branch to merge into (defaults to task.base_branch)
            delete_branch: Whether to delete the task branch after merge

        Returns:
            Commit hash of the merge commit

        Raises:
            ValueError: If merge fails or task has no branch name
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch name configured")

        git = GitRepoIntegration(task.codebase.local_path)

        # Use task's base_branch if target not specified
        target = target_branch or task.base_branch

        # Perform the merge
        merge_commit = await git.merge_branch(task.branch_name, target, no_ff=True)
        logfire.info(f"Merged branch {task.branch_name} into {target} for task {task.id}")

        # Optionally delete the branch
        if delete_branch:
            await git.delete_branch(task.branch_name, force=False)
            logfire.info(f"Deleted branch {task.branch_name} after merge for task {task.id}")

        return merge_commit

    async def delete_task_branch(self, task: Task, force: bool = False) -> None:
        """Delete a task's git branch.

        Args:
            task: Task instance
            force: Force deletion even if not fully merged

        Raises:
            ValueError: If deletion fails or task has no branch name
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch name configured")

        git = GitRepoIntegration(task.codebase.local_path)

        await git.delete_branch(task.branch_name, force=force)
        logfire.info(f"Deleted branch {task.branch_name} for task {task.id}")

    async def get_task_all_changes(self, task: Task) -> StructuredDiff:
        """Get all changes for a task (from merge base to current state).

        If a worktree slot exists, this includes committed changes plus uncommitted changes.
        If no worktree slot exists, this shows only committed changes on the task branch.

        Args:
            task: Task instance

        Returns:
            StructuredDiff with all changes from merge base to current state
        """
        # Get the most recently used worktree slot for this task
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)

        if last_used_slot:
            # Use worktree path - includes uncommitted changes
            git = GitRepoIntegration(last_used_slot.path)
            # Get merge base comparing base branch to HEAD (task branch in worktree)
            merge_base = await git.get_merge_base(task.base_branch, "HEAD")
            # Get all changes from merge base to working directory (includes uncommitted)
            return await git.get_structured_diff(commit1=merge_base)
        else:
            # No worktree - use main codebase path, compare to task branch (committed changes only)
            if not task.branch_name:
                # No branch yet, return empty diff
                return StructuredDiff(files=[], additions=0, deletions=0)

            git = GitRepoIntegration(task.codebase.local_path)
            # Get merge base comparing base branch to task branch
            merge_base = await git.get_merge_base(task.base_branch, task.branch_name)
            # Get changes from merge base to task branch (committed changes only)
            return await git.get_structured_diff(commit1=merge_base, commit2=task.branch_name)

    async def get_task_uncommitted_changes(self, task: Task) -> StructuredDiff:
        """Get uncommitted changes for a task.

        Only checks for uncommitted changes in the task's worktree slot.
        Returns empty diff if no worktree slot exists for the task.

        Args:
            task: Task instance

        Returns:
            StructuredDiff with uncommitted changes, or empty diff if no worktree slot
        """
        # Get the most recently used worktree slot for this task
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)

        # If no worktree slot, return empty diff
        if not last_used_slot:
            return StructuredDiff(files=[], additions=0, deletions=0)

        # Get uncommitted changes from the worktree
        git = GitRepoIntegration(last_used_slot.path)
        return await git.get_structured_diff(commit1="HEAD")

    async def get_task_commit_diff(self, task: Task, commit_hash: str) -> CommitDiff:
        """Get diff for a specific commit in the task branch.

        Commits are repository-wide, so always uses the main codebase path.

        Args:
            task: Task instance
            commit_hash: Commit hash to get diff for

        Returns:
            CommitDiff with commit metadata and files
        """
        git = GitRepoIntegration(task.codebase.local_path)
        return await git.get_structured_commit_diff(commit_hash)

    async def get_task_diff_by_view(self, task: Task, view: str) -> StructuredDiff:
        """Get task diff based on view type.

        Automatically determines the appropriate repository path based on view type:
        - ALL/UNCOMMITTED: Uses worktree slot if available
        - Commit hash: Uses main codebase path

        Args:
            task: Task instance
            view: View type (all/uncommitted/<commit_hash>) - required

        Returns:
            StructuredDiff with files for the requested view

        Raises:
            ValueError: If view is invalid
        """
        # Handle different view types
        if view == TaskDiffView.ALL:
            # Get all changes (uses worktree slot if available, otherwise committed changes only)
            return await self.get_task_all_changes(task)

        elif view == TaskDiffView.UNCOMMITTED:
            # Get only uncommitted changes (uses worktree slot internally)
            return await self.get_task_uncommitted_changes(task)

        else:
            # Assume it's a commit hash - get diff for specific commit (uses main codebase)
            commit_diff = await self.get_task_commit_diff(task, view)
            # Convert CommitDiff to StructuredDiff (just the files)
            return StructuredDiff(
                files=commit_diff.files,
                additions=commit_diff.additions,
                deletions=commit_diff.deletions,
            )
