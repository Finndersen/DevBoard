"""Merge strategy implementations for task feature branch merging."""

from abc import ABC, abstractmethod

import logfire

from devboard.db.models.codebase import MergeMethod
from devboard.db.models.task import Task
from devboard.integrations.git import GitRepoIntegration
from devboard.services.task_git.types import MergeOutcome, MergeResult, _stash_conflict_message


class MergeStrategy(ABC):
    """Abstract base class for merge strategies."""

    @abstractmethod
    async def execute(self, task: Task, git: GitRepoIntegration) -> MergeResult:
        """Execute the merge strategy and return the result."""
        ...


def get_merge_strategy(merge_method: MergeMethod) -> "MergeStrategy":
    """Return the merge strategy instance for the given merge method."""
    strategies: dict[MergeMethod, type[MergeStrategy]] = {
        MergeMethod.SQUASH: SquashMerge,
        MergeMethod.REBASE: RebaseMerge,
        MergeMethod.MERGE_COMMIT: MergeCommitMerge,
    }
    strategy_class = strategies.get(merge_method)
    if strategy_class is None:
        raise ValueError(f"Invalid merge method for local branch merge: {merge_method}")
    return strategy_class()


class SquashMerge(MergeStrategy):
    """Squashes all commits into one and merges into base branch."""

    async def execute(self, task: Task, git: GitRepoIntegration) -> MergeResult:
        merge_method = MergeMethod.SQUASH
        is_remote_base = task.base_branch.startswith("origin/")

        stash_ref = await git.stash(f"DevBoard: pre-merge stash for task {task.id}")

        try:
            if is_remote_base:
                merge_commit = await self._squash_merge_to_remote_base(task, git)
            else:
                merge_commit = await self._squash_merge_to_local_base(task, git)

            await git.delete_branch(task.branch_name, force=True)
            logfire.info(f"Deleted local branch {task.branch_name}")

            if await git.is_branch_pushed(task.branch_name):
                try:
                    await git.push_delete_branch(task.branch_name)
                    logfire.info(f"Deleted remote branch {task.branch_name}")
                except Exception as e:
                    logfire.warning(f"Could not delete remote branch: {e}")
        except Exception:
            if stash_ref:
                try:
                    await git.stash_pop()
                except Exception as pop_err:
                    logfire.warning(f"Failed to restore stash after merge failure for task {task.id}: {pop_err}")
            raise

        if stash_ref:
            try:
                await git.stash_pop()
            except Exception as pop_err:
                logfire.warning(f"Stash pop had conflicts after merge for task {task.id}: {pop_err}")
                return MergeResult(
                    outcome=MergeOutcome.STASH_CONFLICT,
                    merge_method=merge_method,
                    message=_stash_conflict_message(git.repo_path),
                    merge_commit=merge_commit,
                )

        return MergeResult(
            outcome=MergeOutcome.SUCCESS,
            merge_method=merge_method,
            message=f"Successfully squash merged {task.branch_name} into {task.base_branch}",
            merge_commit=merge_commit,
        )

    async def _squash_merge_to_local_base(self, task: Task, git: GitRepoIntegration) -> str:
        base_branch = task.base_branch
        checkout_path = await git.get_checked_out_location(base_branch)

        if checkout_path:
            worktree_git = GitRepoIntegration(checkout_path)
            return await worktree_git.merge_squash(
                source=task.branch_name,
                target=base_branch,
                title=task.title,
            )
        else:
            current_branch = await git.get_current_branch()
            try:
                return await git.merge_squash(
                    source=task.branch_name,
                    target=base_branch,
                    title=task.title,
                )
            finally:
                if current_branch != task.branch_name:
                    await git.checkout_branch(current_branch)

    async def _squash_merge_to_remote_base(self, task: Task, git: GitRepoIntegration) -> str:
        local_base = task.base_branch.replace("origin/", "")
        await git._run_git_command(["fetch", "origin", local_base])
        merge_commit = await git.merge_squash(
            source=task.branch_name,
            target=local_base,
            title=task.title,
        )
        await git.push_branch(local_base, set_upstream=False)
        return merge_commit


class RebaseMerge(MergeStrategy):
    """Rebases feature branch onto base, then fast-forward merges."""

    async def execute(self, task: Task, git: GitRepoIntegration) -> MergeResult:
        merge_method = MergeMethod.REBASE
        is_remote_base = task.base_branch.startswith("origin/")

        stash_ref = await git.stash(f"DevBoard: pre-merge stash for task {task.id}")

        try:
            await git.rebase_branch(task.branch_name, task.base_branch)
            logfire.info(f"Rebased {task.branch_name} onto {task.base_branch}")

            if is_remote_base:
                local_base = task.base_branch.replace("origin/", "")
                await git._run_git_command(["push", "origin", f"{task.branch_name}:{local_base}"])
                merge_commit = await git._run_git_command(["rev-parse", task.branch_name])
            else:
                checkout_path = await git.get_checked_out_location(task.base_branch)
                if checkout_path:
                    worktree_git = GitRepoIntegration(checkout_path)
                    merge_commit = await worktree_git.fast_forward_merge(
                        source=task.branch_name,
                        target=task.base_branch,
                    )
                else:
                    current_branch = await git.get_current_branch()
                    try:
                        merge_commit = await git.fast_forward_merge(
                            source=task.branch_name,
                            target=task.base_branch,
                        )
                    finally:
                        if current_branch != task.branch_name:
                            await git.checkout_branch(current_branch)

            await git.delete_branch(task.branch_name, force=True)
            if await git.is_branch_pushed(task.branch_name):
                try:
                    await git.push_delete_branch(task.branch_name)
                except Exception as e:
                    logfire.warning(f"Could not delete remote branch: {e}")
        except Exception:
            if stash_ref:
                try:
                    await git.stash_pop()
                except Exception as pop_err:
                    logfire.warning(f"Failed to restore stash after merge failure for task {task.id}: {pop_err}")
            raise

        if stash_ref:
            try:
                await git.stash_pop()
            except Exception as pop_err:
                logfire.warning(f"Stash pop had conflicts after merge for task {task.id}: {pop_err}")
                return MergeResult(
                    outcome=MergeOutcome.STASH_CONFLICT,
                    merge_method=merge_method,
                    message=_stash_conflict_message(git.repo_path),
                    merge_commit=merge_commit,
                )

        return MergeResult(
            outcome=MergeOutcome.SUCCESS,
            merge_method=merge_method,
            message=f"Successfully rebased and merged {task.branch_name} into {task.base_branch}",
            merge_commit=merge_commit,
        )


class MergeCommitMerge(MergeStrategy):
    """Creates a merge commit preserving full history."""

    async def execute(self, task: Task, git: GitRepoIntegration) -> MergeResult:
        merge_method = MergeMethod.MERGE_COMMIT
        is_remote_base = task.base_branch.startswith("origin/")

        stash_ref = await git.stash(f"DevBoard: pre-merge stash for task {task.id}")

        try:
            if is_remote_base:
                local_base = task.base_branch.replace("origin/", "")
                await git._run_git_command(["fetch", "origin", local_base])
                current_branch = await git.get_current_branch()
                await git.checkout_branch(local_base)
                try:
                    merge_commit = await git.merge_branch(task.branch_name, local_base, no_ff=True)
                    await git.push_branch(local_base, set_upstream=False)
                finally:
                    if current_branch != task.branch_name:
                        await git.checkout_branch(current_branch)
            else:
                checkout_path = await git.get_checked_out_location(task.base_branch)
                if checkout_path:
                    worktree_git = GitRepoIntegration(checkout_path)
                    merge_commit = await worktree_git.merge_branch(task.branch_name, task.base_branch, no_ff=True)
                else:
                    current_branch = await git.get_current_branch()
                    await git.checkout_branch(task.base_branch)
                    try:
                        merge_commit = await git.merge_branch(task.branch_name, task.base_branch, no_ff=True)
                    finally:
                        if current_branch != task.branch_name:
                            await git.checkout_branch(current_branch)

            await git.delete_branch(task.branch_name, force=True)
            if await git.is_branch_pushed(task.branch_name):
                try:
                    await git.push_delete_branch(task.branch_name)
                except Exception as e:
                    logfire.warning(f"Could not delete remote branch: {e}")
        except Exception:
            if stash_ref:
                try:
                    await git.stash_pop()
                except Exception as pop_err:
                    logfire.warning(f"Failed to restore stash after merge failure for task {task.id}: {pop_err}")
            raise

        if stash_ref:
            try:
                await git.stash_pop()
            except Exception as pop_err:
                logfire.warning(f"Stash pop had conflicts after merge for task {task.id}: {pop_err}")
                return MergeResult(
                    outcome=MergeOutcome.STASH_CONFLICT,
                    merge_method=merge_method,
                    message=_stash_conflict_message(git.repo_path),
                    merge_commit=merge_commit,
                )

        return MergeResult(
            outcome=MergeOutcome.SUCCESS,
            merge_method=merge_method,
            message=f"Successfully merged {task.branch_name} into {task.base_branch} with merge commit",
            merge_commit=merge_commit,
        )
