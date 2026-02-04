"""Service for task git operations.

Handles git branch operations for tasks including branch creation,
status checking, merging, and deletion.
"""

from dataclasses import dataclass
from enum import StrEnum

import logfire

from devboard.db.models.codebase import MergeMethod
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
    merge_method: MergeMethod
    message: str
    merge_commit: str | None = None


class RebaseOutcome(StrEnum):
    """Outcome of a rebase operation."""

    SUCCESS = "success"  # Rebase completed successfully
    CONFLICT = "conflict"  # Rebase has conflicts that need resolution
    STASH_CONFLICT = "stash_conflict"  # Rebase succeeded but stash apply had conflicts


@dataclass
class BaseBranchChanges:
    """Changes in the base branch since last rebase/sync.

    Captures information about what changed in the base branch between
    the previous and current HEAD after fetching from remote.
    """

    commits: list[GitLogEntry]
    files_changed: list[str]
    additions: int
    deletions: int
    fork_point: str
    base_head: str

    def format_summary(self, base_branch: str, max_files: int = 20) -> str:
        """Format a human-readable summary of the base branch changes.

        Args:
            base_branch: Name of the base branch for display
            max_files: Maximum number of files to list before truncating

        Returns:
            Formatted markdown summary of the changes
        """
        commit_list = "\n".join(f"  - {c.hash[:7]}: {c.subject}" for c in self.commits)
        file_list = "\n".join(f"  - {f}" for f in self.files_changed[:max_files])
        if len(self.files_changed) > max_files:
            file_list += f"\n  - ... and {len(self.files_changed) - max_files} more files"

        return (
            f"**Base branch ({base_branch}) changes since last sync** "
            f"({len(self.commits)} commits, {len(self.files_changed)} files, "
            f"+{self.additions}/-{self.deletions}):\n\n"
            f"**Commits:**\n{commit_list}\n\n"
            f"**Files changed:**\n{file_list}"
        )


@dataclass
class RebaseResult:
    """Result of a rebase operation."""

    outcome: RebaseOutcome
    slot_path: str
    new_head: str | None = None  # Set when rebase completes successfully
    conflicted_files: list[str] | None = None  # Set when there are conflicts
    has_pending_stash: bool = False  # True if uncommitted changes are stashed waiting to be restored
    base_branch_changes: BaseBranchChanges | None = None  # Changes in base branch since last sync


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
        """Ensure task's git branch exists, creating it if necessary.

        This method is called at the start of the implementation phase to ensure
        the task has a git branch to work on. The branch_name must already be set
        on the task (generated at task creation time).

        Args:
            task: Task instance with branch_name set

        Returns:
            The branch name

        Raises:
            ValueError: If task.branch_name is not set
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} must have branch_name set")

        branch_name = task.branch_name

        # Create branch if it doesn't exist
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
            - rebase_in_progress: bool

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

        # Check for rebase in progress in the task's working directory
        rebase_in_progress = False
        if worktree_slot_path:
            worktree_git = GitRepoIntegration(worktree_slot_path)
            rebase_in_progress = worktree_git.is_rebase_in_progress()

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
                "rebase_in_progress": rebase_in_progress,
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
                "rebase_in_progress": rebase_in_progress,
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
            "rebase_in_progress": rebase_in_progress,
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

    # Message pattern for identifying rebase stashes
    REBASE_STASH_MESSAGE_PREFIX = "DevBoard: rebase stash for task"

    def _get_rebase_stash_message(self, task_id: int) -> str:
        """Get the stash message for a task's rebase operation."""
        return f"{self.REBASE_STASH_MESSAGE_PREFIX} {task_id}"

    async def rebase_task_branch(self, task: Task) -> RebaseResult:
        """Rebase a task's branch onto its base branch (idempotent).

        This method handles the complete rebase lifecycle:
        - If rebase is already in progress: attempts to continue
        - If no rebase in progress: starts new rebase (stashing uncommitted changes first)
        - On conflict: returns CONFLICT outcome with list of conflicted files
        - On success: applies stashed changes (if any), returns SUCCESS outcome

        The rebase is performed from the worktree where the branch is checked out (if any),
        otherwise from the main repository.

        Args:
            task: Task instance

        Returns:
            RebaseResult with outcome, new HEAD (if successful), and conflict info (if applicable)

        Raises:
            ValueError: If task has no branch name configured
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch name configured")

        # Use the worktree slot path if available, otherwise main repo
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)
        repo_path = last_used_slot.path if last_used_slot else task.codebase.local_path

        git = GitRepoIntegration(repo_path)
        stash_message = self._get_rebase_stash_message(task.id)

        # Check if rebase is already in progress
        if git.is_rebase_in_progress():
            return await self._continue_rebase(task, git, repo_path, stash_message)

        # No rebase in progress - start a new one
        return await self._start_rebase(task, git, repo_path, stash_message)

    async def _continue_rebase(
        self, task: Task, git: GitRepoIntegration, repo_path: str, stash_message: str
    ) -> RebaseResult:
        """Continue an in-progress rebase."""
        try:
            new_head = await git.rebase_continue()
            logfire.info(f"Rebase continued successfully for task {task.id}")
            # Rebase complete - try to restore stashed changes
            return await self._apply_rebase_stash_if_exists(task, git, repo_path, stash_message, new_head)
        except RebaseConflictError:
            # Still have conflicts (files still contain conflict markers)
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
        # Stash uncommitted changes if any (with identifiable message)
        if await git.has_uncommitted_changes():
            await git.stash_push(include_untracked=True, message=stash_message)
            logfire.info(f"Stashed uncommitted changes for task {task.id}")

        # Get fork point - where task branch diverged from base branch
        fork_point = await git.get_fork_point(task.base_branch, task.branch_name)

        # Fetch latest from remote to ensure we have up-to-date base branch
        try:
            await git.fetch()
        except ShellCommandExecutionError:
            # Fetch failure is non-fatal - continue with local state
            pass

        # Get current base branch HEAD after fetch
        base_head_current = await git.get_branch_head(task.base_branch)

        # Compute base branch changes between fork point and current base HEAD
        base_branch_changes: BaseBranchChanges | None = None
        if fork_point and base_head_current and fork_point != base_head_current:
            try:
                commits = await git.get_commits_in_range(fork_point, base_head_current)
                diff = await git.get_structured_diff(fork_point, base_head_current)
                base_branch_changes = BaseBranchChanges(
                    commits=commits,
                    files_changed=[f.file_path for f in diff.files],
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

        # Start the rebase (don't abort on conflict - leave paused)
        try:
            new_head = await git.rebase_branch(task.branch_name, task.base_branch, abort_on_conflict=False)
            logfire.info(f"Rebased branch {task.branch_name} onto {task.base_branch} for task {task.id}")
            # Rebase complete - try to restore stashed changes
            return await self._apply_rebase_stash_if_exists(
                task, git, repo_path, stash_message, new_head, base_branch_changes
            )
        except RebaseConflictError:
            # Rebase has conflicts
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

        # Found a rebase stash - try to apply it
        try:
            await git.stash_apply(stash_ref)
            # Drop the stash after successful apply
            await git.stash_drop(stash_ref)
            logfire.info(f"Restored stashed changes after rebase for task {task.id}")
            return RebaseResult(
                outcome=RebaseOutcome.SUCCESS,
                slot_path=repo_path,
                new_head=new_head,
                base_branch_changes=base_branch_changes,
            )
        except ShellCommandExecutionError:
            # Stash apply had conflicts
            conflicted_files = await git.get_conflicted_files()
            logfire.warning(f"Stash apply had conflicts for task {task.id}")
            return RebaseResult(
                outcome=RebaseOutcome.STASH_CONFLICT,
                slot_path=repo_path,
                new_head=new_head,
                conflicted_files=conflicted_files,
                base_branch_changes=base_branch_changes,
            )

    async def merge_task_feature_branch(self, task: Task) -> MergeResult:
        """Merge a task's feature branch into its base branch based on codebase merge method.

        This method handles the complete merge workflow:
        1. Validates merge method compatibility with codebase config
        2. Stashes uncommitted changes if present
        3. Executes method-specific merge
        4. Cleans up feature branch
        5. Unstashes changes

        Args:
            task: Task instance with branch_name set

        Returns:
            MergeResult with outcome and relevant details

        Raises:
            ValueError: If task has no branch, or if merge method is invalid
        """
        if not task.branch_name:
            raise ValueError("Task has no branch name configured")

        merge_method = MergeMethod(task.codebase.merge_method)
        codebase = task.codebase

        # Get git integration for main repo
        git = GitRepoIntegration(codebase.local_path)

        # Check for conflicts before attempting merge
        comparison = await git.get_branch_comparison(task.branch_name, task.base_branch)
        if comparison.has_conflicts:
            return MergeResult(
                outcome=MergeOutcome.CONFLICT,
                merge_method=merge_method,
                message=f"Cannot merge: conflicts detected between {task.branch_name} and {task.base_branch}",
            )

        # Check if branch is already merged (no new commits)
        if comparison.ahead == 0:
            return MergeResult(
                outcome=MergeOutcome.SKIPPED,
                merge_method=merge_method,
                message=f"Branch {task.branch_name} has no new commits - already merged or up-to-date with {task.base_branch}",
            )

        # Release feature branch if checked out in a worktree
        # Required for rebase (implicit checkout) and delete_branch
        release_result = await git.release_branch_from_worktree(task.branch_name)
        if release_result.worktree_path:
            logfire.info(f"Released branch {task.branch_name} from worktree {release_result.worktree_path}")

        # Execute method-specific merge
        try:
            if merge_method == MergeMethod.SQUASH:
                return await self._execute_squash_merge(task, git)
            elif merge_method == MergeMethod.REBASE:
                return await self._execute_rebase_merge(task, git)
            elif merge_method == MergeMethod.MERGE_COMMIT:
                return await self._execute_merge_commit_merge(task, git)
            else:
                raise ValueError(f"Invalid merge method for local branch merge: {merge_method}")
        except Exception as e:
            logfire.error(f"Merge failed for task {task.id}: {e}")
            return MergeResult(
                outcome=MergeOutcome.ERROR,
                merge_method=merge_method,
                message=f"Merge failed: {str(e)}",
            )

    async def _execute_squash_merge(self, task: Task, git: GitRepoIntegration) -> MergeResult:
        """Execute squash merge method.

        Squashes all commits into one and merges into base branch.
        """
        merge_method = MergeMethod.SQUASH
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
                merge_method=merge_method,
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
        """Execute rebase merge method.

        Rebases feature branch onto base, then fast-forward merges.
        """
        merge_method = MergeMethod.REBASE
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
                merge_method=merge_method,
                message=f"Successfully rebased and merged {task.branch_name} into {task.base_branch}",
                merge_commit=merge_commit,
            )
        finally:
            if stash_ref:
                await git.stash_pop()

    async def _execute_merge_commit_merge(self, task: Task, git: GitRepoIntegration) -> MergeResult:
        """Execute merge commit method.

        Creates a merge commit preserving full history.
        """
        merge_method = MergeMethod.MERGE_COMMIT
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
                merge_method=merge_method,
                message=f"Successfully merged {task.branch_name} into {task.base_branch} with merge commit",
                merge_commit=merge_commit,
            )
        finally:
            if stash_ref:
                await git.stash_pop()

    async def abort_rebase(self, task: Task) -> None:
        """Abort an in-progress rebase for a task.

        Args:
            task: Task instance

        Raises:
            ValueError: If task has no branch or no rebase is in progress
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch name configured")

        # Use the worktree slot path if available, otherwise main repo
        last_used_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)
        repo_path = last_used_slot.path if last_used_slot else task.codebase.local_path

        git = GitRepoIntegration(repo_path)

        if not git.is_rebase_in_progress():
            raise ValueError("No rebase is currently in progress")

        await git.rebase_abort()
        logfire.info(f"Aborted rebase for task {task.id}")
