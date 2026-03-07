"""Backwards-compatibility shim — import from devboard.services.workspace instead."""

from devboard.services.workspace import (  # noqa: F401
    AllSlotsLockedException,
    BranchInUseException,
    LastUsedByTaskInfo,
    LockedByTaskInfo,
    PoolStats,
    PoolStatus,
    SetupCommandError,
    SlotInfo,
    WorkspaceAllocationService,
)
