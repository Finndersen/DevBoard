"""Service for task git operations.

Handles git branch operations for tasks including branch creation,
status checking, merging, and deletion.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

import logfire

from devboard.db.models.codebase import MergeStrategy
from devboard.db.models.task import Task
from devboard.db.repositories.task import TaskRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import RebaseConflictError, ShellCommandExecutionError
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


class MergeOutcome(StrEnum):
    """Outcome of a merge operation."""

    SUCCESS = "success"  # Merge completed successfully
    CONFLICT = "conflict"  # Merge blocked due to conflicts
    SKIPPED = "skipped"  # No merge performed (e.g., 'none' strategy)
    ERROR = "error"  # Merge failed due to an error


@dataclass
class MergeResult:
    """Result of a task merge operation."""

    outcome: MergeOutcome
    strategy: MergeStrategy
    message: str
    merge_commit: str | None = None


@dataclass
class RebaseResult:
    """Result of a rebase operation."""

    new_head: str
    slot_path: str
    had_uncommitted_changes: bool
    uncommitted_changes_restored: bool
    has_stash_conflicts: bool = False


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

        # Get fork point to find where task branch diverged from base
        # This works correctly even after the branch has been merged
        fork_point = await git.get_fork_point(task.base_branch, task.branch_name)

        if not fork_point:
            return []

        # Get commits in the task branch since fork point
        commits = await git.get_commits_in_range(fork_point, task.branch_name)

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
            - worktree_slot_path: str | None
            - main_repo_is_clean: bool
            - main_repo_current_branch: str | None

        Raises:
            ValueError: If task configuration is invalid
        """
        # Get worktree slot info
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)
        worktree_slot_path = last_used_slot.path if last_used_slot else None

        # Get main repo status
        main_git = GitRepoIntegration(task.codebase.local_path)
        main_repo_is_clean = not await main_git.has_uncommitted_changes()
        main_repo_current_branch = await main_git.get_current_branch()

        if not task.branch_name:
            return {
                "branch_name": None,
                "branch_exists": False,
                "base_branch": task.base_branch,
                "commits_ahead": 0,
                "commits_behind": 0,
                "can_merge": False,
                "has_conflicts": False,
                "worktree_slot_path": worktree_slot_path,
                "main_repo_is_clean": main_repo_is_clean,
                "main_repo_current_branch": main_repo_current_branch,
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
                "worktree_slot_path": worktree_slot_path,
                "main_repo_is_clean": main_repo_is_clean,
                "main_repo_current_branch": main_repo_current_branch,
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
            "worktree_slot_path": worktree_slot_path,
            "main_repo_is_clean": main_repo_is_clean,
            "main_repo_current_branch": main_repo_current_branch,
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
            # Stage untracked files with intent-to-add so they appear in diff
            await git.stage_untracked_files_intent()
            # Get fork point - use task.branch_name for reflog lookup, not "HEAD"
            # The reflog "branch: Created from" entry is on the branch, not on HEAD
            feature_branch = task.branch_name if task.branch_name else "HEAD"
            fork_point = await git.get_fork_point(task.base_branch, feature_branch)
            if not fork_point:
                return StructuredDiff(files=[], additions=0, deletions=0)
            # Get all changes from fork point to working directory (includes uncommitted)
            return await git.get_structured_diff(commit1=fork_point)
        else:
            assert task.branch_name is not None
            git = GitRepoIntegration(task.codebase.local_path)
            # Get fork point - works correctly even after branch has been merged
            fork_point = await git.get_fork_point(task.base_branch, task.branch_name)
            if not fork_point:
                return StructuredDiff(files=[], additions=0, deletions=0)
            # Get changes from fork point to task branch (committed changes only)
            return await git.get_structured_diff(commit1=fork_point, commit2=task.branch_name)

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
        # Stage untracked files with intent-to-add so they appear in diff
        await git.stage_untracked_files_intent()
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

    async def rebase_task_branch(self, task: Task) -> RebaseResult:
        """Rebase a task's branch onto its base branch.

        This brings the task branch up-to-date with the latest changes in the base branch.
        Uncommitted changes are stashed before rebase and restored after.

        The rebase is performed from the worktree where the branch is checked out (if any),
        otherwise from the main repository.

        Args:
            task: Task instance

        Returns:
            RebaseResult with new HEAD, stash status, and pending stash ref if conflicts

        Raises:
            ValueError: If task has no branch name configured
            RebaseConflictError: If rebase encounters conflicts (stash is restored first)
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch name configured")

        # Use the worktree slot path if available, otherwise main repo
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)
        repo_path = last_used_slot.path if last_used_slot else task.codebase.local_path

        git = GitRepoIntegration(repo_path)

        # Stash uncommitted changes (including untracked files)
        # stash_push automatically cleans the working tree
        had_uncommitted = await git.has_uncommitted_changes()
        stash_ref: str | None = None
        if had_uncommitted:
            stash_ref = await git.stash_push(include_untracked=True)
            logfire.info(f"Stashed uncommitted changes for task {task.id}")

        uncommitted_restored = False
        has_stash_conflicts = False

        try:
            # Fetch latest from remote to ensure we have up-to-date base branch
            await git.fetch()

            # Perform rebase - this will raise RebaseConflictError if there are conflicts
            new_head = await git.rebase_onto(task.base_branch)
            logfire.info(f"Rebased branch {task.branch_name} onto {task.base_branch} for task {task.id}")
        except RebaseConflictError:
            # Restore stashed changes before re-raising
            if stash_ref:
                await git.stash_apply(stash_ref)
                logfire.info(f"Restored stashed changes after rebase conflict for task {task.id}")
            raise

        # Apply stash after successful rebase
        if stash_ref:
            try:
                await git.stash_apply(stash_ref)
                uncommitted_restored = True
                logfire.info(f"Restored stashed changes after rebase for task {task.id}")
            except ShellCommandExecutionError:
                # Stash apply had conflicts - leave files in conflicted state
                # Agent will resolve conflicts from the partially-applied files
                has_stash_conflicts = True
                logfire.warning(f"Stash apply had conflicts for task {task.id}")

        return RebaseResult(
            new_head=new_head,
            slot_path=repo_path,
            had_uncommitted_changes=had_uncommitted,
            uncommitted_changes_restored=uncommitted_restored,
            has_stash_conflicts=has_stash_conflicts,
        )

    async def checkout_task_to_main_repo(self, task: Task) -> None:
        """Checkout a task's branch to the main repository.

        This flow:
        1. Gets the last used worktree slot for the task
        2. Stashes uncommitted changes in the worktree (if any)
        3. Detaches HEAD in that worktree (to release the branch)
        4. Checks out the task's branch in the main repository
        5. Applies the stashed changes to the main repository
        6. Updates the task's worktree slot assignment to the main repo slot

        Args:
            task: Task instance

        Raises:
            ValueError: If task has no branch name, main repo is dirty, or operation fails
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch name configured")

        main_git = GitRepoIntegration(task.codebase.local_path)

        # Check main repo is clean
        if await main_git.has_uncommitted_changes():
            raise ValueError("Main repository has uncommitted changes")

        # Get last used slot for the task
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)

        stash_sha: str | None = None

        # If the branch is checked out in a worktree, stash changes and detach HEAD
        if last_used_slot and not last_used_slot.is_main_repo:
            slot_git = GitRepoIntegration(last_used_slot.path)
            current_branch = await slot_git.get_current_branch()

            # Only process if the task's branch is actually checked out there
            if current_branch == task.branch_name:
                # Stash uncommitted changes (including untracked files)
                stash_sha = await slot_git.stash_create(include_untracked=True)
                if stash_sha:
                    await slot_git.reset_working_tree(include_untracked=True)
                    logfire.info(f"Stashed uncommitted changes in worktree {last_used_slot.path} for task {task.id}")

                await slot_git.switch_detach()
                logfire.info(f"Detached HEAD in worktree {last_used_slot.path} for task {task.id}")

        # Checkout branch in main repository
        await main_git.checkout_branch(task.branch_name)
        logfire.info(f"Checked out branch {task.branch_name} in main repo for task {task.id}")

        # Apply stashed changes to main repository
        if stash_sha:
            await main_git.stash_apply(stash_sha)
            logfire.info(f"Applied stashed changes to main repo for task {task.id}")

        # Find the main repo slot and lock it for this task
        main_slot = self.worktree_slot_repo.get_main_slot_for_codebase(task.codebase_id)
        if main_slot:
            self.worktree_slot_repo.lock_slot(main_slot, task)
            logfire.info(f"Assigned main repo slot to task {task.id}")

    async def complete_task_merge(self, task: Task) -> MergeResult:
        """Complete a task by merging its feature branch based on codebase merge strategy.

        This method handles the complete merge workflow:
        1. Validates strategy compatibility with codebase config
        2. Stashes uncommitted changes if present
        3. Executes strategy-specific merge
        4. Cleans up feature branch
        5. Unstashes changes

        Args:
            task: Task instance with branch_name set

        Returns:
            MergeResult with outcome and relevant details

        Raises:
            ValueError: If task has no branch, or if GITHUB_PR strategy is used
                (GITHUB_PR should be handled via dedicated workflow action)
        """
        if not task.branch_name:
            raise ValueError("Task has no branch name configured")

        strategy = MergeStrategy(task.codebase.merge_strategy)
        codebase = task.codebase

        # GITHUB_PR strategy must be handled via dedicated workflow action
        if strategy == MergeStrategy.GITHUB_PR:
            raise ValueError(
                "GitHub PR strategy should be handled via create_pull_request workflow action, "
                "not complete_task_merge()"
            )

        # For 'none' strategy, just return skipped without any git operations
        if strategy == MergeStrategy.NONE:
            return MergeResult(
                outcome=MergeOutcome.SKIPPED,
                strategy=strategy,
                message="Manual merge strategy - no git operations performed",
            )

        # Get git integration for main repo
        git = GitRepoIntegration(codebase.local_path)

        # Check for conflicts before attempting merge
        comparison = await git.get_branch_comparison(task.branch_name, task.base_branch)
        if comparison.has_conflicts:
            return MergeResult(
                outcome=MergeOutcome.CONFLICT,
                strategy=strategy,
                message=f"Cannot merge: conflicts detected between {task.branch_name} and {task.base_branch}",
            )

        # Execute strategy-specific merge
        try:
            if strategy == MergeStrategy.SQUASH:
                return await self._execute_squash_merge(task, git)
            elif strategy == MergeStrategy.REBASE:
                return await self._execute_rebase_merge(task, git)
            elif strategy == MergeStrategy.MERGE_COMMIT:
                return await self._execute_merge_commit_merge(task, git)
            else:
                return MergeResult(
                    outcome=MergeOutcome.ERROR,
                    strategy=strategy,
                    message=f"Unknown merge strategy: {strategy}",
                )
        except Exception as e:
            logfire.error(f"Merge failed for task {task.id}: {e}")
            return MergeResult(
                outcome=MergeOutcome.ERROR,
                strategy=strategy,
                message=f"Merge failed: {str(e)}",
            )

    async def _execute_squash_merge(self, task: Task, git: GitRepoIntegration) -> MergeResult:
        """Execute squash merge strategy.

        Squashes all commits into one and merges into base branch.
        """
        strategy = MergeStrategy.SQUASH
        is_remote_base = task.base_branch.startswith("origin/")

        # Stash any uncommitted changes
        stash_ref = await git.stash(f"DevBoard: pre-merge stash for task {task.id}")

        try:
            if is_remote_base:
                # Remote base: squash merge locally then push
                merge_commit = await self._squash_merge_to_remote_base(task, git)
            else:
                # Local base: find worktree with base branch, squash merge there
                merge_commit = await self._squash_merge_to_local_base(task, git)

            # Delete the feature branch (local)
            await git.delete_branch(task.branch_name, force=True)
            logfire.info(f"Deleted local branch {task.branch_name}")

            # If branch was pushed, delete from remote
            if await git.is_branch_pushed(task.branch_name):
                try:
                    await git.push_delete_branch(task.branch_name)
                    logfire.info(f"Deleted remote branch {task.branch_name}")
                except Exception as e:
                    logfire.warning(f"Could not delete remote branch: {e}")

            return MergeResult(
                outcome=MergeOutcome.SUCCESS,
                strategy=strategy,
                message=f"Successfully squash merged {task.branch_name} into {task.base_branch}",
                merge_commit=merge_commit,
            )
        finally:
            # Always restore stashed changes
            if stash_ref:
                await git.stash_pop()

    async def _squash_merge_to_local_base(self, task: Task, git: GitRepoIntegration) -> str:
        """Squash merge into a local base branch."""
        base_branch = task.base_branch

        # Check if base branch is checked out somewhere
        checkout_path = await git.get_checked_out_location(base_branch)

        if checkout_path:
            # Use the worktree where base branch is checked out
            worktree_git = GitRepoIntegration(checkout_path)
            # Stash if dirty
            worktree_stash = await worktree_git.stash("DevBoard: temp stash for merge")
            try:
                merge_commit = await worktree_git.merge_squash(
                    source=task.branch_name,
                    target=base_branch,
                    title=task.title,
                )
                return merge_commit
            finally:
                if worktree_stash:
                    await worktree_git.stash_pop()
        else:
            # merge_squash handles checkout internally now
            merge_commit = await git.merge_squash(
                source=task.branch_name,
                target=base_branch,
                title=task.title,
            )
            return merge_commit

    async def _squash_merge_to_remote_base(self, task: Task, git: GitRepoIntegration) -> str:
        """Squash merge into a remote base branch."""
        # Extract local branch name from remote (e.g., 'origin/main' -> 'main')
        local_base = task.base_branch.replace("origin/", "")

        # Fetch latest from remote
        await git._run_git_command(["fetch", "origin", local_base])

        # merge_squash handles checkout internally
        merge_commit = await git.merge_squash(
            source=task.branch_name,
            target=local_base,
            title=task.title,
        )
        # Push to remote
        await git.push_branch(local_base, set_upstream=False)
        return merge_commit

    async def _execute_rebase_merge(self, task: Task, git: GitRepoIntegration) -> MergeResult:
        """Execute rebase merge strategy.

        Rebases feature branch onto base, then fast-forward merges.
        """
        strategy = MergeStrategy.REBASE
        is_remote_base = task.base_branch.startswith("origin/")

        # Stash any uncommitted changes
        stash_ref = await git.stash(f"DevBoard: pre-merge stash for task {task.id}")

        try:
            # Rebase feature branch onto base
            await git.rebase_branch(task.branch_name, task.base_branch)
            logfire.info(f"Rebased {task.branch_name} onto {task.base_branch}")

            if is_remote_base:
                # Remote base: push the rebased branch directly
                local_base = task.base_branch.replace("origin/", "")
                # Force push rebased feature branch as the new base
                await git._run_git_command(["push", "origin", f"{task.branch_name}:{local_base}"])
                merge_commit = await git._run_git_command(["rev-parse", task.branch_name])
            else:
                # Local base: fast-forward merge
                checkout_path = await git.get_checked_out_location(task.base_branch)
                if checkout_path:
                    worktree_git = GitRepoIntegration(checkout_path)
                    merge_commit = await worktree_git.fast_forward_merge(
                        source=task.branch_name,
                        target=task.base_branch,
                    )
                else:
                    # fast_forward_merge handles checkout internally
                    merge_commit = await git.fast_forward_merge(
                        source=task.branch_name,
                        target=task.base_branch,
                    )

            # Delete the feature branch
            await git.delete_branch(task.branch_name, force=True)
            if await git.is_branch_pushed(task.branch_name):
                try:
                    await git.push_delete_branch(task.branch_name)
                except Exception as e:
                    logfire.warning(f"Could not delete remote branch: {e}")

            return MergeResult(
                outcome=MergeOutcome.SUCCESS,
                strategy=strategy,
                message=f"Successfully rebased and merged {task.branch_name} into {task.base_branch}",
                merge_commit=merge_commit,
            )
        finally:
            if stash_ref:
                await git.stash_pop()

    async def _execute_merge_commit_merge(self, task: Task, git: GitRepoIntegration) -> MergeResult:
        """Execute merge commit strategy.

        Creates a merge commit preserving full history.
        """
        strategy = MergeStrategy.MERGE_COMMIT
        is_remote_base = task.base_branch.startswith("origin/")

        # Stash any uncommitted changes
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
                    await git.checkout_branch(current_branch)
            else:
                # Local base
                checkout_path = await git.get_checked_out_location(task.base_branch)
                if checkout_path:
                    worktree_git = GitRepoIntegration(checkout_path)
                    worktree_stash = await worktree_git.stash("DevBoard: temp stash")
                    try:
                        merge_commit = await worktree_git.merge_branch(task.branch_name, task.base_branch, no_ff=True)
                    finally:
                        if worktree_stash:
                            await worktree_git.stash_pop()
                else:
                    current_branch = await git.get_current_branch()
                    await git.checkout_branch(task.base_branch)
                    try:
                        merge_commit = await git.merge_branch(task.branch_name, task.base_branch, no_ff=True)
                    finally:
                        await git.checkout_branch(current_branch)

            # Delete the feature branch
            await git.delete_branch(task.branch_name, force=True)
            if await git.is_branch_pushed(task.branch_name):
                try:
                    await git.push_delete_branch(task.branch_name)
                except Exception as e:
                    logfire.warning(f"Could not delete remote branch: {e}")

            return MergeResult(
                outcome=MergeOutcome.SUCCESS,
                strategy=strategy,
                message=f"Successfully merged {task.branch_name} into {task.base_branch} with merge commit",
                merge_commit=merge_commit,
            )
        finally:
            if stash_ref:
                await git.stash_pop()
