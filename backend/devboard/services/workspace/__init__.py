"""Workspace package."""

from devboard.config.integration_configs import WorktreeLocationMode
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
from devboard.services.workspace.workspace_service import WorkspaceService

__all__ = [
    "WorkspaceService",
    "WorktreeLocationMode",
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
