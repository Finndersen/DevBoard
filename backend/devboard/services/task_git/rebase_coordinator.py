"""Rebase coordination for task branches."""

import logfire

from devboard.db.models.task import NoWorktreeAllocatedException, Task
from devboard.integrations.git import GitRepoIntegration, parse_remote_branch
from devboard.integrations.shell import RebaseConflictError, ShellCommandExecutionError
from devboard.services.task_git.types import BaseBranchChanges, RebaseOutcome, RebaseResult, TaskConfigurationError


class TaskRebaseCoordinator:
    """Handles rebase operations for task branches."""

    REBASE_STASH_MESSAGE_PREFIX = "DevBoard: rebase stash for task"

    @classmethod
    async def rebase_task_branch(cls, task: Task) -> RebaseResult:
        """Rebase a task's branch onto its base branch (idempotent).

        Handles the complete rebase lifecycle:
        - If rebase is already in progress: attempts to continue
        - If no rebase in progress: starts new rebase (stashing uncommitted changes first)
        - On conflict: returns CONFLICT outcome with list of conflicted files
        - On success: applies stashed changes (if any), returns SUCCESS outcome

        Raises:
            ValueError: If task has no branch name configured or no workspace allocated
        """
        if not task.branch_name:
            raise TaskConfigurationError(f"Task {task.id} has no branch name configured")

        slot = task.last_used_worktree_slot
        if slot is None:
            raise NoWorktreeAllocatedException(
                f"Task {task.id} has no workspace allocated. Allocate a workspace before calling rebase_task_branch."
            )
        repo_path = slot.path

        git = GitRepoIntegration(repo_path)
        stash_message = f"{cls.REBASE_STASH_MESSAGE_PREFIX} {task.id}"

        if git.is_rebase_in_progress():
            return await cls._continue_rebase(task, git, repo_path, stash_message)

        return await cls._start_rebase(task, git, repo_path, stash_message)

    @classmethod
    async def _continue_rebase(
        cls, task: Task, git: GitRepoIntegration, repo_path: str, stash_message: str
    ) -> RebaseResult:
        """Continue an in-progress rebase."""
        try:
            new_head = await git.rebase_continue()
            logfire.info(f"Rebase continued successfully for task {task.id}")
            return await cls._apply_rebase_stash_if_exists(task, git, repo_path, stash_message, new_head)
        except RebaseConflictError:
            conflicted_files = await git.get_conflicted_files()
            has_pending_stash = await git.find_stash_by_message(stash_message) is not None
            return RebaseResult(
                outcome=RebaseOutcome.CONFLICT,
                slot_path=repo_path,
                conflicted_files=conflicted_files,
                has_pending_stash=has_pending_stash,
            )

    @classmethod
    async def _start_rebase(
        cls, task: Task, git: GitRepoIntegration, repo_path: str, stash_message: str
    ) -> RebaseResult:
        """Start a new rebase operation."""
        stash_ref = await git.stash_push(include_untracked=True, message=stash_message)
        if stash_ref:
            logfire.info(f"Stashed uncommitted changes for task {task.id}")

        fork_point = await git.get_fork_point(task.base_branch, task.branch_name)

        task_files_changed: list[str] = []
        if fork_point:
            try:
                task_files_changed = await git.get_changed_file_paths(fork_point, task.branch_name)
            except Exception as e:
                logfire.warning(f"Failed to compute task branch changed files: {e}")

        remotes = await git.list_remotes()
        parsed = parse_remote_branch(task.base_branch, remotes)
        if parsed:
            remote, branch = parsed
            try:
                await git.fetch(remote=remote, branch=branch)
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
            return await cls._apply_rebase_stash_if_exists(
                task, git, repo_path, stash_message, new_head, base_branch_changes, task_files_changed
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
                task_files_changed=task_files_changed,
            )

    @classmethod
    async def _apply_rebase_stash_if_exists(
        cls,
        task: Task,
        git: GitRepoIntegration,
        repo_path: str,
        stash_message: str,
        new_head: str,
        base_branch_changes: BaseBranchChanges | None = None,
        task_files_changed: list[str] | None = None,
    ) -> RebaseResult:
        """Check for and apply any rebase stash after successful rebase."""
        stash_ref = await git.find_stash_by_message(stash_message)

        task_files = task_files_changed or []

        if not stash_ref:
            return RebaseResult(
                outcome=RebaseOutcome.SUCCESS,
                slot_path=repo_path,
                new_head=new_head,
                base_branch_changes=base_branch_changes,
                task_files_changed=task_files,
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
                task_files_changed=task_files,
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
                task_files_changed=task_files,
            )
