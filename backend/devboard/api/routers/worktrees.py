"""Worktree pool management API endpoints."""

from fastapi import APIRouter, Depends

from devboard.api.dependencies.entities import get_verified_codebase
from devboard.api.dependencies.services import get_workspace_allocation_service
from devboard.api.schemas import (
    WorktreePoolStatusResponse,
    WorktreeSlotWithTaskInfo,
)
from devboard.db.models import Codebase
from devboard.services.workspace_allocation_service import WorkspaceAllocationService

router = APIRouter()


@router.get("/codebases/{codebase_id}/worktree-pool", response_model=WorktreePoolStatusResponse)
async def get_worktree_pool_status(
    codebase_id: int,
    codebase: Codebase = Depends(get_verified_codebase),
    workspace_allocation_service: WorkspaceAllocationService = Depends(get_workspace_allocation_service),
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
        workspace_allocation_service: Worktree pool service

    Returns:
        Worktree pool status with all slots
    """
    pool_status = await workspace_allocation_service.get_pool_status_for_codebase(codebase)

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
