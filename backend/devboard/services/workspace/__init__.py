"""Workspace allocation package."""

from devboard.services.workspace.allocation_service import WorkspaceAllocationService
from devboard.services.workspace.pool_manager import WorktreePoolManager
from devboard.services.workspace.types import (
    AllSlotsLockedException,
    BranchInUseException,
    LastUsedByTaskInfo,
    LockedByTaskInfo,
    PoolStats,
    PoolStatus,
    SetupCommandError,
    SlotInfo,
)

__all__ = [
    "WorkspaceAllocationService",
    "WorktreePoolManager",
    "AllSlotsLockedException",
    "BranchInUseException",
    "LastUsedByTaskInfo",
    "LockedByTaskInfo",
    "PoolStats",
    "PoolStatus",
    "SetupCommandError",
    "SlotInfo",
]
