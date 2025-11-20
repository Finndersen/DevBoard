"""Worktree pool management API endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.entities import get_verified_codebase
from devboard.api.dependencies.repositories import get_task_repository, get_worktree_slot_repository
from devboard.api.dependencies.services import (
    get_worktree_pool_service,
)
from devboard.api.schemas import (
    ReconcileWorktreePoolResponse,
    WorktreePoolStatusResponse,
    WorktreeSlotWithTaskInfo,
)
from devboard.db.models import Codebase
from devboard.db.repositories import TaskRepository, WorktreeSlotRepository
from devboard.services.worktree_pool_service import WorktreePoolService

router = APIRouter()


@router.get("/codebases/{codebase_id}/worktree-pool", response_model=WorktreePoolStatusResponse)
async def get_worktree_pool_status(
    codebase_id: int,
    codebase: Codebase = Depends(get_verified_codebase),
    pool_service: WorktreePoolService = Depends(get_worktree_pool_service),
    task_repo: TaskRepository = Depends(get_task_repository),
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
        pool_service: Worktree pool service
        task_repo: Task repository

    Returns:
        Worktree pool status with all slots
    """
    pool_status = await asyncio.to_thread(pool_service.get_pool_status, codebase_id)

    # Enhance slots with task information - pool_status already includes this
    slots_with_info: list[WorktreeSlotWithTaskInfo] = []
    for slot_dict in pool_status["slots"]:
        slots_with_info.append(WorktreeSlotWithTaskInfo(**slot_dict))

    return WorktreePoolStatusResponse(
        codebase_id=codebase_id,
        codebase_path=codebase.local_path,
        slots=slots_with_info,
        stats=pool_status["stats"],
    )


@router.post("/codebases/{codebase_id}/worktree-pool/reconcile", response_model=ReconcileWorktreePoolResponse)
async def reconcile_worktree_pool(
    codebase_id: int,
    codebase: Codebase = Depends(get_verified_codebase),
    pool_service: WorktreePoolService = Depends(get_worktree_pool_service),
    slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
) -> ReconcileWorktreePoolResponse:
    """Reconcile worktree pool state with actual git worktrees.

    Syncs the database with the actual git worktree state:
    - Removes DB slots for deleted worktrees
    - Adds DB slots for manually created worktrees
    - Releases all locks (conservative on reconciliation)

    Args:
        codebase_id: ID of the codebase
        codebase: Codebase instance
        pool_service: Worktree pool service
        slot_repo: Worktree slot repository

    Returns:
        Reconciliation results

    Raises:
        HTTPException: 400 if reconciliation fails
    """
    try:
        result = await asyncio.to_thread(pool_service.reconcile_state, codebase_id)
        slot_repo.db.commit()
        return ReconcileWorktreePoolResponse(
            success=True,
            message=result["message"],
            slots_removed=result["slots_removed"],
            slots_added=result["slots_added"],
            locks_released=result["locks_released"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
