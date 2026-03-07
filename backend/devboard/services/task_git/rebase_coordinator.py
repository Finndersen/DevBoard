"""Rebase coordination for task branches."""

import logfire

from devboard.db.models.task import Task
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import RebaseConflictError, ShellCommandExecutionError
from devboard.services.task_git.types import BaseBranchChanges, RebaseOutcome, RebaseResult


class TaskRebaseCoordinator:
    """Handles rebase operations for task branches."""

    REBASE_STASH_MESSAGE_PREFIX = "DevBoard: rebase stash for task"

    def __init__(self, worktree_slot_repo: WorktreeSlotRepository):
        self.worktree_slot_repo = worktree_slot_repo

    def _get_rebase_stash_message(self, task_id: int) -> str:
        return f"{self.REBASE_STASH_MESSAGE_PREFIX} {task_id}"

    async def rebase_task_branch(self, task: Task) -> RebaseResult:
        """Rebase a task's branch onto its base branch (idempotent).

        Handles the complete rebase lifecycle:
        - If rebase is already in progress: attempts to continue
        - If no rebase in progress: starts new rebase (stashing uncommitted changes first)
        - On conflict: returns CONFLICT outcome with list of conflicted files
        - On success: applies stashed changes (if any), returns SUCCESS outcome

        Raises:
            ValueError: If task has no branch name configured
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch name configured")

        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)
        repo_path = last_used_slot.path if last_used_slot else task.codebase.local_path

        git = GitRepoIntegration(repo_path)
        stash_message = self._get_rebase_stash_message(task.id)

        if git.is_rebase_in_progress():
            return await self._continue_rebase(task, git, repo_path, stash_message)

        return await self._start_rebase(task, git, repo_path, stash_message)

    async def _continue_rebase(
        self, task: Task, git: GitRepoIntegration, repo_path: str, stash_message: str
    ) -> RebaseResult:
        """Continue an in-progress rebase."""
        try:
            new_head = await git.rebase_continue()
            logfire.info(f"Rebase continued successfully for task {task.id}")
            return await self._apply_rebase_stash_if_exists(task, git, repo_path, stash_message, new_head)
        except RebaseConflictError:
            conflicted_files = await git.get_conflicted_files()
            has_pending_stash = await git.find_stash_by_message(stash_message) is not None
            return RebaseResult(
                outcome=RebaseOutcome.CONFLICT,
                slot_path=repo_path,
                conflicted_files=conflicted_files,
                has_pending_stash=has_pending_stash,
            )

    async def _start_rebase(
        self, task: Task, git: GitRepoIntegration, repo_path: str, stash_message: str
    ) -> RebaseResult:
        """Start a new rebase operation."""
        if await git.has_uncommitted_changes():
            await git.stash_push(include_untracked=True, message=stash_message)
            logfire.info(f"Stashed uncommitted changes for task {task.id}")

        fork_point = await git.get_fork_point(task.base_branch, task.branch_name)

        try:
            await git.fetch()
        except ShellCommandExecutionError:
            pass  # Fetch failure is non-fatal - continue with local state

        base_head_current = await git.get_branch_head(task.base_branch)

        base_branch_changes: BaseBranchChanges | None = None
        if fork_point and base_head_current and fork_point != base_head_current:
            try:
                commits = await git.get_commits_in_range(fork_point, base_head_current)
                diff = await git.get_structured_diff(fork_point, base_head_current)
                base_branch_changes = BaseBranchChanges(
                    commits=commits,
                    files_changed=diff.files,
                    additions=diff.additions,
                    deletions=diff.deletions,
                    fork_point=fork_point,
                    base_head=base_head_current,
                )
                logfire.info(
                    f"Base branch {task.base_branch} changed since fork: {len(commits)} commits, "
                    f"{len(base_branch_changes.files_changed)} files changed"
                )
            except Exception as e:
                logfire.warning(f"Failed to compute base branch changes: {e}")

        try:
            new_head = await git.rebase_branch(task.branch_name, task.base_branch, abort_on_conflict=False)
            logfire.info(f"Rebased branch {task.branch_name} onto {task.base_branch} for task {task.id}")
            return await self._apply_rebase_stash_if_exists(
                task, git, repo_path, stash_message, new_head, base_branch_changes
            )
        except RebaseConflictError:
            conflicted_files = await git.get_conflicted_files()
            has_pending_stash = await git.find_stash_by_message(stash_message) is not None
            logfire.info(f"Rebase encountered conflicts for task {task.id}")
            return RebaseResult(
                outcome=RebaseOutcome.CONFLICT,
                slot_path=repo_path,
                conflicted_files=conflicted_files,
                has_pending_stash=has_pending_stash,
                base_branch_changes=base_branch_changes,
            )

    async def _apply_rebase_stash_if_exists(
        self,
        task: Task,
        git: GitRepoIntegration,
        repo_path: str,
        stash_message: str,
        new_head: str,
        base_branch_changes: BaseBranchChanges | None = None,
    ) -> RebaseResult:
        """Check for and apply any rebase stash after successful rebase."""
        stash_ref = await git.find_stash_by_message(stash_message)

        if not stash_ref:
            return RebaseResult(
                outcome=RebaseOutcome.SUCCESS,
                slot_path=repo_path,
                new_head=new_head,
                base_branch_changes=base_branch_changes,
            )

        try:
            await git.stash_apply(stash_ref)
            await git.stash_drop(stash_ref)
            logfire.info(f"Restored stashed changes after rebase for task {task.id}")
            return RebaseResult(
                outcome=RebaseOutcome.SUCCESS,
                slot_path=repo_path,
                new_head=new_head,
                base_branch_changes=base_branch_changes,
            )
        except ShellCommandExecutionError:
            conflicted_files = await git.get_conflicted_files()
            logfire.warning(f"Stash apply had conflicts for task {task.id}")
            return RebaseResult(
                outcome=RebaseOutcome.STASH_CONFLICT,
                slot_path=repo_path,
                new_head=new_head,
                conflicted_files=conflicted_files,
                base_branch_changes=base_branch_changes,
            )
