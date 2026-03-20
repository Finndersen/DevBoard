"""TaskGitService: orchestrates git operations for tasks."""

import logfire

from devboard.db.models.codebase import MergeMethod
from devboard.db.models.task import Task
from devboard.integrations.git import GitRepoIntegration, parse_remote_branch
from devboard.integrations.shell import ShellCommandError
from devboard.integrations.types import CommitDiff, GitLogEntry, StructuredDiff
from devboard.services.task_git.merge_strategy import get_merge_strategy
from devboard.services.task_git.rebase_coordinator import TaskRebaseCoordinator
from devboard.services.task_git.types import MergeOutcome, MergeResult, RebaseResult, TaskDiffView, TaskGitStatus


class TaskBranchNotFoundException(Exception):
    def __init__(self, branch_name: str, task_id: int):
        super().__init__(
            f"Task branch '{branch_name}' does not exist. It may have been deleted or is not available on this machine."
        )
        self.branch_name = branch_name
        self.task_id = task_id


class TaskGitService:
    """Service for task git operations."""

    async def _fetch_remote_gracefully(self, git: GitRepoIntegration, base_branch: str) -> bool:
        """Attempt to fetch the base branch from remote, returning success status.

        Returns True if fetch succeeded or branch is local (no fetch needed).
        Returns False if remote fetch failed (logged as warning).
        """
        remotes = await git.list_remotes()
        parsed = parse_remote_branch(base_branch, remotes)
        if parsed is None:
            return True
        remote, branch = parsed
        try:
            await git.fetch(remote=remote, branch=branch, timeout=10.0)
            return True
        except ShellCommandError as e:
            logfire.warn(f"Remote fetch failed for base branch '{base_branch}' (proceeding with local state): {e}")
            return False

    async def create_task_branch(self, task: Task) -> str:
        """Ensure task's git branch exists, creating it if necessary.

        Args:
            task: Task instance with branch_name set

        Returns:
            The branch name
        """
        branch_name = task.branch_name

        git = GitRepoIntegration(task.codebase.local_path)

        if not await git.branch_exists(branch_name):
            await self._fetch_remote_gracefully(git, task.base_branch)
            await git.create_branch(branch_name, task.base_branch)
            logfire.info(f"Created branch {branch_name} from {task.base_branch} for task {task.id}")
        else:
            logfire.info(f"Branch {branch_name} already exists for task {task.id}")

        return branch_name

    async def verify_task_branch_exists(self, task: Task) -> None:
        git = GitRepoIntegration(task.codebase.local_path)
        if not await git.branch_exists(task.branch_name):
            raise TaskBranchNotFoundException(
                branch_name=task.branch_name,
                task_id=task.id,
            )

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
        last_used_slot = task.last_used_worktree_slot
        worktree_slot_path = last_used_slot.path if last_used_slot else None

        main_git = GitRepoIntegration(task.codebase.local_path)
        main_repo_is_clean = not await main_git.has_uncommitted_changes()
        main_repo_current_branch = await main_git.get_current_branch()

        rebase_in_progress = False
        worktree_git = None
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

        fetch_succeeded = await self._fetch_remote_gracefully(git, task.base_branch)

        comparison = await git.get_branch_comparison(task.branch_name, task.base_branch)

        has_uncommitted_base_overlap = False
        if worktree_git and branch_exists:
            uncommitted_files = await worktree_git.get_uncommitted_file_paths()
            if uncommitted_files:
                fork_point = await git.get_fork_point(task.base_branch, task.branch_name)
                if fork_point:
                    base_changed_files = await git.get_changed_file_paths(fork_point, task.base_branch)
                    has_uncommitted_base_overlap = bool(set(uncommitted_files) & set(base_changed_files))

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
            has_uncommitted_base_overlap=has_uncommitted_base_overlap,
            remote_fetch_failed=not fetch_succeeded,
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

    async def get_task_all_changes(self, task: Task) -> StructuredDiff:
        """Get all changes for a task (from merge base to current state).

        If a worktree slot exists, this includes committed changes plus uncommitted changes.
        If no worktree slot exists, this shows only committed changes on the task branch.
        """
        last_used_slot = task.last_used_worktree_slot
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
        last_used_slot = task.last_used_worktree_slot
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

    async def rebase_task_branch(self, task: Task) -> RebaseResult:
        return await TaskRebaseCoordinator.rebase_task_branch(task)

    async def abort_rebase(self, task: Task) -> None:
        """Abort an in-progress rebase for a task."""
        last_used_slot = task.last_used_worktree_slot
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

        # Check for uncommitted changes in base branch workdir that overlap with
        # feature branch changes. Non-overlapping uncommitted changes are safe —
        # the merge strategies already handle stash/unstash.
        checkout_path = await git.get_checked_out_location(task.base_branch)
        if checkout_path:
            base_git = GitRepoIntegration(checkout_path)
            uncommitted_files = await base_git.get_uncommitted_file_paths()
            if uncommitted_files:
                feature_files = await git.get_changed_file_paths(task.base_branch, task.branch_name)
                overlapping = set(uncommitted_files) & set(feature_files)
                if overlapping:
                    file_list = "\n".join(f"  - {f}" for f in sorted(overlapping))
                    return MergeResult(
                        outcome=MergeOutcome.ERROR,
                        merge_method=merge_method,
                        message=f"Cannot merge: uncommitted changes in '{checkout_path}' overlap with feature branch changes:\n{file_list}\nPlease commit or stash these files first.",
                    )

        release_result = await git.release_branch_from_worktree(task.branch_name)
        if release_result.worktree_path:
            logfire.info(f"Released branch {task.branch_name} from worktree {release_result.worktree_path}")

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
