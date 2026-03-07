"""TaskGitService: orchestrates git operations for tasks."""

import logfire

from devboard.db.models.codebase import MergeMethod
from devboard.db.models.task import Task
from devboard.db.repositories.task import TaskRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.types import GitLogEntry
from devboard.services.task_git.diff_service import TaskDiffService
from devboard.services.task_git.merge_strategy import get_merge_strategy
from devboard.services.task_git.rebase_coordinator import TaskRebaseCoordinator
from devboard.services.task_git.types import MergeOutcome, MergeResult, RebaseResult, TaskDiffView, TaskGitStatus


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
        self._diff_service = TaskDiffService(worktree_slot_repo)

    async def ensure_task_branch(self, task: Task) -> str:
        """Ensure task's git branch exists, creating it if necessary.

        Args:
            task: Task instance with branch_name set

        Returns:
            The branch name
        """
        branch_name = task.branch_name

        git = GitRepoIntegration(task.codebase.local_path)
        if not await git.branch_exists(branch_name):
            await git.create_branch(branch_name, task.base_branch)
            logfire.info(f"Created branch {branch_name} from {task.base_branch} for task {task.id}")
        else:
            logfire.info(f"Branch {branch_name} already exists for task {task.id}")

        return branch_name

    async def get_task_commit_metadata(self, task: Task) -> list[GitLogEntry]:
        """Get lightweight commit metadata for a task branch.

        Returns commit metadata (hash, author, date, message) without file diffs.
        Used for populating UI dropdowns. Always runs against main codebase path.
        """
        git = GitRepoIntegration(task.codebase.local_path)
        fork_point = await git.get_fork_point(task.base_branch, task.branch_name)

        if not fork_point:
            return []

        return await git.get_commits_in_range(fork_point, task.branch_name)

    async def get_task_git_status(self, task: Task) -> TaskGitStatus:
        """Get git status for a task's branch."""
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)
        worktree_slot_path = last_used_slot.path if last_used_slot else None

        main_git = GitRepoIntegration(task.codebase.local_path)
        main_repo_is_clean = not await main_git.has_uncommitted_changes()
        main_repo_current_branch = await main_git.get_current_branch()

        rebase_in_progress = False
        if worktree_slot_path:
            worktree_git = GitRepoIntegration(worktree_slot_path)
            rebase_in_progress = worktree_git.is_rebase_in_progress()

        git = GitRepoIntegration(task.codebase.local_path)
        branch_exists = await git.branch_exists(task.branch_name)

        if not branch_exists:
            return TaskGitStatus(
                branch_name=task.branch_name,
                branch_exists=False,
                base_branch=task.base_branch,
                commits_ahead=0,
                commits_behind=0,
                can_merge=False,
                has_conflicts=False,
                worktree_slot_path=worktree_slot_path,
                main_repo_is_clean=main_repo_is_clean,
                main_repo_current_branch=main_repo_current_branch,
                rebase_in_progress=rebase_in_progress,
            )

        comparison = await git.get_branch_comparison(task.branch_name, task.base_branch)

        return TaskGitStatus(
            branch_name=task.branch_name,
            branch_exists=True,
            base_branch=task.base_branch,
            commits_ahead=comparison.ahead,
            commits_behind=comparison.behind,
            can_merge=comparison.can_merge,
            has_conflicts=comparison.has_conflicts,
            worktree_slot_path=worktree_slot_path,
            main_repo_is_clean=main_repo_is_clean,
            main_repo_current_branch=main_repo_current_branch,
            rebase_in_progress=rebase_in_progress,
        )

    async def merge_task_branch(
        self,
        task: Task,
        target_branch: str | None = None,
        delete_branch: bool = False,
    ) -> str:
        """Merge a task's branch into its base branch.

        Returns:
            Commit hash of the merge commit
        """
        git = GitRepoIntegration(task.codebase.local_path)
        target = target_branch or task.base_branch
        merge_commit = await git.merge_branch(task.branch_name, target, no_ff=True)
        logfire.info(f"Merged branch {task.branch_name} into {target} for task {task.id}")

        if delete_branch:
            await git.delete_branch(task.branch_name, force=False)
            logfire.info(f"Deleted branch {task.branch_name} after merge for task {task.id}")

        return merge_commit

    async def delete_task_branch(self, task: Task, force: bool = False) -> None:
        """Delete a task's git branch."""
        git = GitRepoIntegration(task.codebase.local_path)
        await git.delete_branch(task.branch_name, force=force)
        logfire.info(f"Deleted branch {task.branch_name} for task {task.id}")

    # Diff operations — delegate to TaskDiffService

    async def get_task_all_changes(self, task: Task):
        return await self._diff_service.get_task_all_changes(task)

    async def get_task_uncommitted_changes(self, task: Task):
        return await self._diff_service.get_task_uncommitted_changes(task)

    async def get_task_commit_diff(self, task: Task, commit_hash: str):
        return await self._diff_service.get_task_commit_diff(task, commit_hash)

    async def get_task_diff_by_view(self, task: Task, view: TaskDiffView | str):
        return await self._diff_service.get_task_diff_by_view(task, view)

    # Rebase operations — delegate to TaskRebaseCoordinator

    async def rebase_task_branch(self, task: Task) -> RebaseResult:
        return await TaskRebaseCoordinator(self.worktree_slot_repo).rebase_task_branch(task)

    async def abort_rebase(self, task: Task) -> None:
        """Abort an in-progress rebase for a task."""
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)
        repo_path = last_used_slot.path if last_used_slot else task.codebase.local_path

        git = GitRepoIntegration(repo_path)

        if not git.is_rebase_in_progress():
            raise ValueError("No rebase is currently in progress")

        await git.rebase_abort()
        logfire.info(f"Aborted rebase for task {task.id}")

    async def merge_task_feature_branch(self, task: Task) -> MergeResult:
        """Merge a task's feature branch into its base branch based on codebase merge method.

        Validates, pre-checks, then delegates to the appropriate MergeStrategy.
        Only used for LOCAL_MERGE branch handling — base branch is always expected to be a local branch.
        """
        if task.base_branch.startswith("origin/"):
            raise ValueError(
                f"merge_task_feature_branch() requires a local base branch, got remote: '{task.base_branch}'"
            )

        merge_method = MergeMethod(task.codebase.merge_method)
        git = GitRepoIntegration(task.codebase.local_path)

        comparison = await git.get_branch_comparison(task.branch_name, task.base_branch)
        if comparison.has_conflicts:
            return MergeResult(
                outcome=MergeOutcome.CONFLICT,
                merge_method=merge_method,
                message=f"Cannot merge: conflicts detected between {task.branch_name} and {task.base_branch}",
            )

        if comparison.ahead == 0:
            return MergeResult(
                outcome=MergeOutcome.SKIPPED,
                merge_method=merge_method,
                message=f"Branch {task.branch_name} has no new commits - already merged or up-to-date with {task.base_branch}",
            )

        release_result = await git.release_branch_from_worktree(task.branch_name)
        if release_result.worktree_path:
            logfire.info(f"Released branch {task.branch_name} from worktree {release_result.worktree_path}")

        checkout_path = await git.get_checked_out_location(task.base_branch)
        if checkout_path:
            base_git = GitRepoIntegration(checkout_path)
            if await base_git.has_uncommitted_changes():
                return MergeResult(
                    outcome=MergeOutcome.ERROR,
                    merge_method=merge_method,
                    message=f"Cannot merge: the base branch '{task.base_branch}' working directory at '{checkout_path}' has uncommitted changes. Please commit or stash your changes first.",
                )

        strategy = get_merge_strategy(merge_method)
        try:
            return await strategy.execute(task, git)
        except Exception as e:
            logfire.error(f"Merge failed for task {task.id}: {e}")
            return MergeResult(
                outcome=MergeOutcome.ERROR,
                merge_method=merge_method,
                message=f"Merge failed: {str(e)}",
            )
