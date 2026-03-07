"""Task diff service for retrieving file changes on a task branch."""

from devboard.db.models.task import Task
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.types import CommitDiff, StructuredDiff
from devboard.services.task_git.types import TaskDiffView


class TaskDiffService:
    """Handles retrieval of file diffs for task branches."""

    def __init__(self, worktree_slot_repo: WorktreeSlotRepository):
        self.worktree_slot_repo = worktree_slot_repo

    async def get_task_all_changes(self, task: Task) -> StructuredDiff:
        """Get all changes for a task (from merge base to current state).

        If a worktree slot exists, this includes committed changes plus uncommitted changes.
        If no worktree slot exists, this shows only committed changes on the task branch.
        """
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)

        if last_used_slot:
            git = GitRepoIntegration(last_used_slot.path)
            await git.stage_untracked_files_intent()
            fork_point = await git.get_fork_point(task.base_branch, task.branch_name)
            if not fork_point:
                return StructuredDiff(files=[], additions=0, deletions=0)
            return await git.get_structured_diff(commit1=fork_point)
        else:
            git = GitRepoIntegration(task.codebase.local_path)
            fork_point = await git.get_fork_point(task.base_branch, task.branch_name)
            if not fork_point:
                return StructuredDiff(files=[], additions=0, deletions=0)
            return await git.get_structured_diff(commit1=fork_point, commit2=task.branch_name)

    async def get_task_uncommitted_changes(self, task: Task) -> StructuredDiff:
        """Get uncommitted changes for a task.

        Returns empty diff if no worktree slot exists for the task.
        """
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)

        if not last_used_slot:
            return StructuredDiff(files=[], additions=0, deletions=0)

        git = GitRepoIntegration(last_used_slot.path)
        await git.stage_untracked_files_intent()
        return await git.get_structured_diff(commit1="HEAD")

    async def get_task_commit_diff(self, task: Task, commit_hash: str) -> CommitDiff:
        """Get diff for a specific commit in the task branch.

        Commits are repository-wide, so always uses the main codebase path.
        """
        git = GitRepoIntegration(task.codebase.local_path)
        return await git.get_structured_commit_diff(commit_hash)

    async def get_task_diff_by_view(self, task: Task, view: TaskDiffView | str) -> StructuredDiff:
        """Get task diff based on view type (all/uncommitted/<commit_hash>).

        Raises:
            ValueError: If view is invalid
        """
        if view == TaskDiffView.ALL:
            return await self.get_task_all_changes(task)
        elif view == TaskDiffView.UNCOMMITTED:
            return await self.get_task_uncommitted_changes(task)
        else:
            commit_diff = await self.get_task_commit_diff(task, view)
            return StructuredDiff(
                files=commit_diff.files,
                additions=commit_diff.additions,
                deletions=commit_diff.deletions,
            )
