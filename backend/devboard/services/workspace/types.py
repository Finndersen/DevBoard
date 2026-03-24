"""Data classes and exceptions for workspace allocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from devboard.db.models import WorktreeSlot


class SetupCommandError(Exception):
    """Raised when a codebase setup command fails."""

    def __init__(self, message: str, command: str, returncode: int | None = None):
        super().__init__(message)
        self.message = message
        self.command = command
        self.returncode = returncode


@dataclass
class LockedByTaskInfo:
    """Information about the task that has locked a slot."""

    id: int
    title: str


@dataclass
class LastUsedByTaskInfo:
    """Information about the last task that used a slot."""

    id: int
    title: str


@dataclass
class SlotInfo:
    """Information about a worktree slot."""

    id: int
    path: str
    is_main_repo: bool
    status: Literal["locked", "available", "missing"]
    current_branch: str | None
    last_used_at: str | None
    locked_by_task: LockedByTaskInfo | None = None
    last_used_by_task: LastUsedByTaskInfo | None = None
    has_uncommitted_changes: bool = False
    uncommitted_change_count: int = 0


@dataclass
class PoolStats:
    """Statistics about the worktree pool."""

    total_slots: int
    available: int
    locked: int


@dataclass
class PoolStatus:
    """Status of all worktree slots for a codebase."""

    codebase_id: int
    codebase_path: str
    slots: list[SlotInfo]
    stats: PoolStats


@dataclass
class AllocationResult:
    slot: WorktreeSlot
    reused: bool


class AllSlotsLockedException(Exception):
    """Raised when all worktree slots are locked and allocation fails."""

    pass


class BranchInUseException(Exception):
    """Raised when a task's branch is already checked out in a locked slot."""

    pass
