"""Merge strategy implementations for task feature branch merging."""

from abc import ABC, abstractmethod

import logfire

from devboard.db.models.codebase import MergeMethod
from devboard.db.models.task import Task
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.types import GitLogEntry
from devboard.services.task_git.types import MergeOutcome, MergeResult, stash_conflict_message


class MergeStrategy(ABC):
    """Abstract base class for merge strategies."""

    @abstractmethod
    async def execute(self, task: Task, repo_git: GitRepoIntegration) -> MergeResult:
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
    """Squashes all commits on the feature branch into one, then fast-forward merges into base.

    The squash is performed in-place on the feature branch (via soft reset + commit),
    keeping the base branch untouched until the final fast-forward step. This ensures
    that if the squash commit fails (e.g. hook timeout), the base branch remains clean.
    """

    async def execute(self, task: Task, repo_git: GitRepoIntegration) -> MergeResult:
        merge_method = MergeMethod.SQUASH
        is_remote_base = task.base_branch.startswith("origin/")

        stash_ref = await repo_git.stash(f"DevBoard: pre-merge stash for task {task.id}")

        try:
            if is_remote_base:
                merge_commit = await self._squash_to_remote_base(task, repo_git)
            else:
                merge_commit = await self._squash_to_local_base(task, repo_git)

            await repo_git.delete_branch(task.branch_name, force=True)
            logfire.info(f"Deleted local branch {task.branch_name}")

            if await repo_git.is_branch_pushed(task.branch_name):
                try:
                    await repo_git.push_delete_branch(task.branch_name)
                    logfire.info(f"Deleted remote branch {task.branch_name}")
                except Exception as e:
                    logfire.warning(f"Could not delete remote branch: {e}")
        except Exception:
            if stash_ref:
                try:
                    await repo_git.stash_pop()
                except Exception as pop_err:
                    logfire.warning(f"Failed to restore stash after merge failure for task {task.id}: {pop_err}")
            raise

        if stash_ref:
            try:
                await repo_git.stash_pop()
            except Exception as pop_err:
                logfire.warning(f"Stash pop had conflicts after merge for task {task.id}: {pop_err}")
                return MergeResult(
                    outcome=MergeOutcome.STASH_CONFLICT,
                    merge_method=merge_method,
                    message=stash_conflict_message(str(repo_git.repo_path)),
                    merge_commit=merge_commit,
                )

        return MergeResult(
            outcome=MergeOutcome.SUCCESS,
            merge_method=merge_method,
            message=f"Successfully squash merged {task.branch_name} into {task.base_branch}",
            merge_commit=merge_commit,
        )

    async def _squash_feature_branch_commits(self, task: Task, repo_git: GitRepoIntegration) -> None:
        """Squash all commits on the feature branch into one in-place (no-op if single commit).

        Uses soft reset + commit with --no-verify on the feature branch itself.
        --no-verify is appropriate here: we're squashing already-verified commits, not
        introducing new code, so re-running hooks would be redundant.
        """
        merge_base = await repo_git.get_merge_base(task.base_branch, task.branch_name)
        commits = await repo_git.get_commits_in_range(merge_base, task.branch_name)

        if len(commits) <= 1:
            return

        message = self._build_squash_message(task, commits)

        feature_path = await repo_git.get_checked_out_location(task.branch_name)
        if feature_path:
            feature_git = GitRepoIntegration(feature_path)
            await feature_git.soft_reset(merge_base)
            await feature_git.commit(message, no_verify=True)
        else:
            current_branch = await repo_git.get_current_branch()
            await repo_git.checkout_branch(task.branch_name)
            try:
                await repo_git.soft_reset(merge_base)
                await repo_git.commit(message, no_verify=True)
            finally:
                await repo_git.checkout_branch(current_branch)

    @staticmethod
    def _build_squash_message(task: Task, commits: list[GitLogEntry]) -> str:
        if task.title:
            message_lines = [task.title, ""]
        else:
            message_lines = [f"Squash merge branch '{task.branch_name}' into {task.base_branch}", ""]
        message_lines.append("Squashed commits:")
        for commit in commits:
            message_lines.append(f"* {commit.subject}")
        return "\n".join(message_lines)

    async def _squash_to_local_base(self, task: Task, repo_git: GitRepoIntegration) -> str:
        await self._squash_feature_branch_commits(task, repo_git)

        checkout_path = await repo_git.get_checked_out_location(task.base_branch)
        if checkout_path:
            worktree_git = GitRepoIntegration(checkout_path)
            return await worktree_git.fast_forward_merge(source=task.branch_name, target=task.base_branch)
        else:
            current_branch = await repo_git.get_current_branch()
            try:
                return await repo_git.fast_forward_merge(source=task.branch_name, target=task.base_branch)
            finally:
                if current_branch != task.branch_name:
                    await repo_git.checkout_branch(current_branch)

    async def _squash_to_remote_base(self, task: Task, repo_git: GitRepoIntegration) -> str:
        local_base = task.base_branch.replace("origin/", "")

        await self._squash_feature_branch_commits(task, repo_git)
        await repo_git.run_git_command(["fetch", "origin", local_base])

        feature_path = await repo_git.get_checked_out_location(task.branch_name)
        if feature_path:
            # Feature is in a worktree — rebase from within it to avoid "already checked out" error
            feature_git = GitRepoIntegration(feature_path)
            await feature_git.rebase_onto(task.base_branch)
        else:
            await repo_git.rebase_branch(task.branch_name, task.base_branch)

        await repo_git.run_git_command(["push", "origin", f"{task.branch_name}:{local_base}"], timeout=60.0)
        return await repo_git.run_git_command(["rev-parse", task.branch_name])


class RebaseMerge(MergeStrategy):
    """Rebases feature branch onto base, then fast-forward merges."""

    async def execute(self, task: Task, repo_git: GitRepoIntegration) -> MergeResult:
        merge_method = MergeMethod.REBASE
        is_remote_base = task.base_branch.startswith("origin/")

        stash_ref = await repo_git.stash(f"DevBoard: pre-merge stash for task {task.id}")

        try:
            await repo_git.rebase_branch(task.branch_name, task.base_branch)
            logfire.info(f"Rebased {task.branch_name} onto {task.base_branch}")

            if is_remote_base:
                local_base = task.base_branch.replace("origin/", "")
                await repo_git.run_git_command(["push", "origin", f"{task.branch_name}:{local_base}"])
                merge_commit = await repo_git.run_git_command(["rev-parse", task.branch_name])
            else:
                checkout_path = await repo_git.get_checked_out_location(task.base_branch)
                if checkout_path:
                    worktree_git = GitRepoIntegration(checkout_path)
                    merge_commit = await worktree_git.fast_forward_merge(
                        source=task.branch_name,
                        target=task.base_branch,
                    )
                else:
                    current_branch = await repo_git.get_current_branch()
                    try:
                        merge_commit = await repo_git.fast_forward_merge(
                            source=task.branch_name,
                            target=task.base_branch,
                        )
                    finally:
                        if current_branch != task.branch_name:
                            await repo_git.checkout_branch(current_branch)

            await repo_git.delete_branch(task.branch_name, force=True)
            if await repo_git.is_branch_pushed(task.branch_name):
                try:
                    await repo_git.push_delete_branch(task.branch_name)
                except Exception as e:
                    logfire.warning(f"Could not delete remote branch: {e}")
        except Exception:
            if stash_ref:
                try:
                    await repo_git.stash_pop()
                except Exception as pop_err:
                    logfire.warning(f"Failed to restore stash after merge failure for task {task.id}: {pop_err}")
            raise

        if stash_ref:
            try:
                await repo_git.stash_pop()
            except Exception as pop_err:
                logfire.warning(f"Stash pop had conflicts after merge for task {task.id}: {pop_err}")
                return MergeResult(
                    outcome=MergeOutcome.STASH_CONFLICT,
                    merge_method=merge_method,
                    message=stash_conflict_message(str(repo_git.repo_path)),
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

    async def execute(self, task: Task, repo_git: GitRepoIntegration) -> MergeResult:
        merge_method = MergeMethod.MERGE_COMMIT
        is_remote_base = task.base_branch.startswith("origin/")

        stash_ref = await repo_git.stash(f"DevBoard: pre-merge stash for task {task.id}")

        try:
            if is_remote_base:
                local_base = task.base_branch.replace("origin/", "")
                await repo_git.run_git_command(["fetch", "origin", local_base])
                current_branch = await repo_git.get_current_branch()
                await repo_git.checkout_branch(local_base)
                try:
                    merge_commit = await repo_git.merge_branch(task.branch_name, local_base, no_ff=True)
                    await repo_git.push_branch(local_base, set_upstream=False)
                finally:
                    if current_branch != task.branch_name:
                        await repo_git.checkout_branch(current_branch)
            else:
                checkout_path = await repo_git.get_checked_out_location(task.base_branch)
                if checkout_path:
                    worktree_git = GitRepoIntegration(checkout_path)
                    merge_commit = await worktree_git.merge_branch(task.branch_name, task.base_branch, no_ff=True)
                else:
                    current_branch = await repo_git.get_current_branch()
                    await repo_git.checkout_branch(task.base_branch)
                    try:
                        merge_commit = await repo_git.merge_branch(task.branch_name, task.base_branch, no_ff=True)
                    finally:
                        if current_branch != task.branch_name:
                            await repo_git.checkout_branch(current_branch)

            await repo_git.delete_branch(task.branch_name, force=True)
            if await repo_git.is_branch_pushed(task.branch_name):
                try:
                    await repo_git.push_delete_branch(task.branch_name)
                except Exception as e:
                    logfire.warning(f"Could not delete remote branch: {e}")
        except Exception:
            if stash_ref:
                try:
                    await repo_git.stash_pop()
                except Exception as pop_err:
                    logfire.warning(f"Failed to restore stash after merge failure for task {task.id}: {pop_err}")
            raise

        if stash_ref:
            try:
                await repo_git.stash_pop()
            except Exception as pop_err:
                logfire.warning(f"Stash pop had conflicts after merge for task {task.id}: {pop_err}")
                return MergeResult(
                    outcome=MergeOutcome.STASH_CONFLICT,
                    merge_method=merge_method,
                    message=stash_conflict_message(str(repo_git.repo_path)),
                    merge_commit=merge_commit,
                )

        return MergeResult(
            outcome=MergeOutcome.SUCCESS,
            merge_method=merge_method,
            message=f"Successfully merged {task.branch_name} into {task.base_branch} with merge commit",
            merge_commit=merge_commit,
        )
