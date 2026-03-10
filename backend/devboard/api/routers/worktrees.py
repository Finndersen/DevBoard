"""Worktree pool management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response

from devboard.api.dependencies.entities import get_verified_codebase, get_verified_worktree_slot
from devboard.api.dependencies.services import get_pool_manager
from devboard.api.schemas import (
    WorktreePoolStatusResponse,
    WorktreeSlotWithTaskInfo,
)
from devboard.db.models import Codebase, WorktreeSlot
from devboard.integrations.git import GitRepoIntegration
from devboard.services.workspace.pool_manager import WorktreePoolManager

router = APIRouter()


@router.get("/codebases/{codebase_id}/worktree-pool", response_model=WorktreePoolStatusResponse)
async def get_worktree_pool_status(
    codebase_id: int,
    codebase: Codebase = Depends(get_verified_codebase),
    pool_manager: WorktreePoolManager = Depends(get_pool_manager),
) -> WorktreePoolStatusResponse:
    """Get worktree pool status for a codebase.

    Returns information about all worktree slots including:
    - Slot paths and status (locked/available)
    - Current branches
    - Locked task information
    - Pool statistics

    Args:
        codebase_id: ID of the codebase
        codebase: Codebase instance
        pool_manager: Worktree pool manager

    Returns:
        Worktree pool status with all slots
    """
    pool_status = await pool_manager.get_pool_status_for_codebase(codebase)

    # Enhance slots with task information - pool_status already includes this
    slots_with_info: list[WorktreeSlotWithTaskInfo] = []
    for slot in pool_status.slots:
        # Convert dataclass to dict for Pydantic schema
        slot_dict = {
            "id": slot.id,
            "path": slot.path,
            "is_main_repo": slot.is_main_repo,
            "status": slot.status,
            "current_branch": slot.current_branch,
            "last_used_at": slot.last_used_at,
            "has_uncommitted_changes": slot.has_uncommitted_changes,
            "uncommitted_change_count": slot.uncommitted_change_count,
        }
        if slot.locked_by_task:
            slot_dict["locked_by_task"] = {
                "id": slot.locked_by_task.id,
                "title": slot.locked_by_task.title,
            }
        if slot.last_used_by_task:
            slot_dict["last_used_by_task"] = {
                "id": slot.last_used_by_task.id,
                "title": slot.last_used_by_task.title,
            }
        slots_with_info.append(WorktreeSlotWithTaskInfo(**slot_dict))

    return WorktreePoolStatusResponse(
        codebase_id=codebase_id,
        codebase_path=codebase.local_path,
        slots=slots_with_info,
        stats={
            "total_slots": pool_status.stats.total_slots,
            "available": pool_status.stats.available,
            "locked": pool_status.stats.locked,
        },
    )


@router.delete("/worktree-slots/{slot_id}", status_code=204)
async def delete_worktree_slot(
    slot_id: int,
    slot: WorktreeSlot = Depends(get_verified_worktree_slot),
    pool_manager: WorktreePoolManager = Depends(get_pool_manager),
) -> Response:
    """Delete a worktree slot.

    Blocks deletion (409 Conflict) if:
    - The slot is the main repository
    - The slot is currently locked (in use by a task)
    - The slot has uncommitted changes or untracked files
    """
    if slot.is_main_repo:
        raise HTTPException(status_code=409, detail="Cannot delete main repository slot")

    if slot.locked:
        raise HTTPException(status_code=409, detail="Cannot delete locked worktree slot (currently in use by a task)")

    git = GitRepoIntegration(slot.path)
    if await git.has_uncommitted_changes(include_untracked=True):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete worktree with uncommitted changes or untracked files",
        )

    await pool_manager.delete_worktree_slot(slot)
    return Response(status_code=204)
