"""Type definitions for integration module return values."""

from dataclasses import dataclass


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""

    path: str
    branch: str
    commit: str
    is_main: bool


@dataclass
class BranchComparison:
    """Comparison information between a branch and its base."""

    ahead: int
    behind: int
    has_conflicts: bool
    can_merge: bool


@dataclass
class GitLogEntry:
    """A single git commit log entry."""

    hash: str
    author: str
    date: str
    subject: str
    body: str | None = None


@dataclass
class FileInfo:
    """File metadata information."""

    path: str
    size: int
    modified: float
    is_file: bool
    is_dir: bool


@dataclass
class FileDiff:
    """A single file's diff information."""

    file_path: str
    diff_content: str
    additions: int
    deletions: int
    is_new_file: bool = False
    is_deleted: bool = False


@dataclass
class CommitDiff:
    """A commit with its diff information."""

    commit_hash: str
    author: str
    date: str
    message: str
    files: list[FileDiff]
    additions: int
    deletions: int


@dataclass
class StructuredDiff:
    """Structured diff with files parsed."""

    files: list[FileDiff]
    additions: int
    deletions: int

    def format_summary(self) -> str:
        """Format a concise summary of file changes for agent prompts.

        Returns:
            Formatted summary with per-file stats, e.g.:
            3 files changed, +45/-12
              - src/foo.py (+30/-5)
              - src/bar.py (+15/-7) (new)
              - src/baz.py (+0/-0) (deleted)
        """
        if not self.files:
            return "No file changes."

        header = f"{len(self.files)} files changed, +{self.additions}/-{self.deletions}"
        file_lines = []
        for f in self.files:
            line = f"  - {f.file_path} (+{f.additions}/-{f.deletions})"
            if f.is_new_file:
                line += " (new)"
            elif f.is_deleted:
                line += " (deleted)"
            file_lines.append(line)

        return header + "\n" + "\n".join(file_lines)


@dataclass
class BranchReleaseResult:
    """Result of releasing a branch from a worktree."""

    worktree_path: str | None
    stash_sha: str | None
