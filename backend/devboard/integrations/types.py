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
    message: str


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
