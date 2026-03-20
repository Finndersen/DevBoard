"""Task git operations package."""

from devboard.services.task_git.service import TaskGitService
from devboard.services.task_git.types import (
    BaseBranchChanges,
    MergeOutcome,
    MergeResult,
    RebaseOutcome,
    RebaseResult,
    TaskDiffResult,
    TaskDiffView,
    TaskGitStatus,
    stash_conflict_message,
)

__all__ = [
    "TaskGitService",
    "BaseBranchChanges",
    "MergeOutcome",
    "MergeResult",
    "RebaseOutcome",
    "RebaseResult",
    "TaskDiffResult",
    "TaskDiffView",
    "TaskGitStatus",
    "stash_conflict_message",
]
