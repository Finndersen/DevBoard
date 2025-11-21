"""Service for task git operations.

Handles git branch operations for tasks including branch creation,
status checking, merging, and deletion.
"""

import re

import logfire

from devboard.db.models.task import Task
from devboard.db.repositories.task import TaskRepository
from devboard.integrations.git import GitRepoIntegration


class TaskGitService:
    """Service for task git operations."""

    def __init__(self, task_repo: TaskRepository | None = None):
        """Initialize service.

        Args:
            task_repo: Optional task repository for updating task.branch_name
        """
        self.task_repo = task_repo

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

            # Update task in database if we have a repository
            if self.task_repo:
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

        Format: feature/task-{id}-{slug}

        Args:
            task: Task instance

        Returns:
            Generated branch name
        """
        # Create slug from title (lowercase, alphanumeric + hyphens only, max 50 chars)
        slug = task.title.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        slug = slug[:50]

        return f"feature/task-{task.id}-{slug}"

    async def create_task_branch(self, task: Task) -> None:
        """Create a git branch for a task.

        Args:
            task: Task instance

        Raises:
            ValueError: If branch creation fails or task has no branch name
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch name configured")

        git = GitRepoIntegration(task.codebase.local_path)

        # Check if branch already exists
        if await git.branch_exists(task.branch_name):
            logfire.warn(f"Branch {task.branch_name} already exists for task {task.id}")
            return

        # Create branch from base branch
        await git.create_branch(task.branch_name, task.base_branch)
        logfire.info(f"Created branch {task.branch_name} for task {task.id}")

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
