"""Backwards-compatibility shim — import from devboard.services.task_git instead."""

from devboard.services.task_git import BaseBranchChanges as BaseBranchChanges
from devboard.services.task_git import MergeOutcome as MergeOutcome
from devboard.services.task_git import MergeResult as MergeResult
from devboard.services.task_git import RebaseOutcome as RebaseOutcome
from devboard.services.task_git import RebaseResult as RebaseResult
from devboard.services.task_git import TaskBranchNotFoundException as TaskBranchNotFoundException
from devboard.services.task_git import TaskDiffResult as TaskDiffResult
from devboard.services.task_git import TaskDiffView as TaskDiffView
from devboard.services.task_git import TaskGitService as TaskGitService
from devboard.services.task_git import TaskGitStatus as TaskGitStatus
