"""Worktree Pydantic schemas."""

import datetime
from typing import Any

from pydantic import BaseModel


class WorktreeSlotResponse(BaseModel):
    """Schema for worktree slot response."""

    id: int
    codebase_id: int
    path: str
    is_main_repo: bool
    locked: bool
    last_used_at: datetime.datetime
    last_used_by_task_id: int | None

    model_config = {"from_attributes": True}


class WorktreeSlotWithTaskInfo(BaseModel):
    """Schema for worktree slot with task info."""

    id: int
    path: str
    is_main_repo: bool
    status: str  # "locked" | "available" | "missing"
    current_branch: str | None
    last_used_at: datetime.datetime | None
    locked_by_task: dict[str, Any] | None = None  # {"id": int, "title": str} - only present if locked
    last_used_by_task: dict[str, Any] | None = (
        None  # {"id": int, "title": str} - only present if available and was previously used
    )
    has_uncommitted_changes: bool = False
    uncommitted_change_count: int = 0


class WorktreePoolStatusResponse(BaseModel):
    """Schema for worktree pool status response."""

    codebase_id: int
    codebase_path: str
    slots: list[WorktreeSlotWithTaskInfo]
    stats: dict[str, Any]  # {"total_slots": int, "available": int, "locked": int}


class WorkspaceAllocationResponse(BaseModel):
    """Schema for workspace allocation response."""

    slot: WorktreeSlotResponse
    branch_checked_out: bool
    ready: bool


class WorkspaceAllocationErrorResponse(BaseModel):
    """Schema for workspace allocation error (all slots locked)."""

    error: str
    locked_by: list[dict[str, Any]]  # [{"task_id": int, "title": str, "slot": str}]
    can_create_new: bool


class CreateWorktreeSlotRequest(BaseModel):
    """Schema for creating a new worktree slot."""

    branch: str | None = None  # Optional branch to checkout


class ReconcileWorktreePoolResponse(BaseModel):
    """Schema for reconcile worktree pool response."""

    success: bool
    message: str
    slots_removed: int
    slots_added: int
    locks_released: int
