"""Backwards-compatibility shim — import from devboard.services.task_git instead."""

from devboard.services.task_git import (  # noqa: F401
    BaseBranchChanges,
    MergeOutcome,
    MergeResult,
    RebaseOutcome,
    RebaseResult,
    TaskDiffResult,
    TaskDiffView,
    TaskGitService,
    TaskGitStatus,
    _stash_conflict_message,
)
