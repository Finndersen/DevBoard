"""Data classes and enums for task git operations."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from devboard.db.models.codebase import MergeMethod
from devboard.integrations.types import CommitDiff, FileDiff, GitLogEntry, StructuredDiff


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
    STASH_CONFLICT = "stash_conflict"  # Merge succeeded but restoring pre-merge stash had conflicts


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
    files_changed: list[FileDiff]
    additions: int
    deletions: int
    fork_point: str
    base_head: str

    def _format_file_entry(self, f: FileDiff) -> str:
        line = f"  - {f.file_path} (+{f.additions}/-{f.deletions})"
        if f.is_new_file:
            line += " (new)"
        elif f.is_deleted:
            line += " (deleted)"
        return line

    def format_summary(self, base_branch: str, max_files: int = 20) -> str:
        """Format a human-readable summary of the base branch changes.

        Args:
            base_branch: Name of the base branch for display
            max_files: Maximum number of files to list before truncating

        Returns:
            Formatted markdown summary of the changes
        """
        commit_list = "\n".join(f"  - {c.hash[:7]}: {c.subject}" for c in self.commits)
        file_list = "\n".join(self._format_file_entry(f) for f in self.files_changed[:max_files])
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


class TaskGitStatus(BaseModel):
    """Git status for a task's branch."""

    branch_name: str
    branch_exists: bool
    base_branch: str
    commits_ahead: int
    commits_behind: int
    can_merge: bool
    has_conflicts: bool
    worktree_slot_path: str | None
    main_repo_is_clean: bool
    main_repo_current_branch: str
    rebase_in_progress: bool
    has_uncommitted_base_overlap: bool = False
    remote_fetch_failed: bool = False


def stash_conflict_message(repo_path: str) -> str:
    """Build a user-facing message for a stash pop conflict after a successful merge."""
    return (
        f"Merge succeeded, but restoring pre-merge stashed changes in '{repo_path}' had conflicts "
        f"(the merged changes touched the same files as your WIP). "
        f"The task has been marked complete. To resolve manually:\n"
        f"1. In '{repo_path}', run `git status` to see conflicted files\n"
        f"2. Resolve the conflict markers in each file\n"
        f"3. Run `git stash drop` to remove the stash entry"
    )
