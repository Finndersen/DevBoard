"""Codebase API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.entities import get_verified_codebase
from devboard.api.dependencies.repositories import get_codebase_repository, get_worktree_slot_repository
from devboard.api.schemas import (
    CodebaseCreate,
    CodebaseResponse,
    CodebaseUpdate,
    DeleteResponse,
)
from devboard.db.models import Codebase, MergeStrategy
from devboard.db.repositories import CodebaseRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration

router = APIRouter()


@router.get("/", response_model=list[CodebaseResponse])
async def list_codebases(
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
):
    """List all codebases."""
    codebases = codebase_repo.get_all()
    return codebases


@router.post("/", response_model=CodebaseResponse)
async def create_codebase(
    codebase: CodebaseCreate,
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
):
    """Create a new codebase."""
    # Validate that the local path exists and is a directory
    path = Path(codebase.local_path).resolve()
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Local path does not exist: {codebase.local_path}")

    if not path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Local path is not a directory: {codebase.local_path}",
        )

    # Auto-detect git remote URL if the directory is a git repository
    git = GitRepoIntegration(codebase.local_path)
    repository_url = await git.detect_git_remote_url()

    # Validate repository has at least one commit
    if not await git.has_commits():
        raise HTTPException(
            status_code=400,
            detail="Repository has no commits. Please make at least one commit before adding as a codebase.",
        )

    # Auto-detect default branch if not provided
    default_branch = codebase.default_branch
    if not default_branch:
        default_branch = await git.get_default_branch()

    # Determine merge strategy: use provided value, or auto-detect based on remote URL
    merge_strategy = codebase.merge_strategy
    if merge_strategy is None:
        # Default to github_pr if remote URL exists, otherwise squash
        merge_strategy = MergeStrategy.GITHUB_PR if repository_url else MergeStrategy.SQUASH

    # Validate github_pr strategy requires a remote URL
    if merge_strategy == MergeStrategy.GITHUB_PR and not repository_url:
        raise HTTPException(
            status_code=400,
            detail="GitHub PR merge strategy requires a repository with a remote URL configured",
        )

    # Create the codebase with auto-detected values
    codebase_data = codebase.model_dump()
    codebase_data["repository_url"] = repository_url
    codebase_data["default_branch"] = default_branch
    codebase_data["merge_strategy"] = merge_strategy.value

    db_codebase = Codebase(**codebase_data)
    created_codebase = codebase_repo.create(db_codebase)
    codebase_repo.db.commit()
    codebase_repo.db.refresh(created_codebase)

    # Bootstrap main repo slot for this codebase
    worktree_slot_repo.create(
        codebase_id=created_codebase.id,
        path=created_codebase.local_path,
        is_main_repo=True,
    )

    return created_codebase


@router.get("/{codebase_id}", response_model=CodebaseResponse)
async def get_codebase(
    codebase_id: int,
    codebase: Codebase = Depends(get_verified_codebase),
):
    """Get a specific codebase."""
    return codebase


@router.patch("/{codebase_id}", response_model=CodebaseResponse)
async def update_codebase(
    codebase_id: int,
    codebase_update: CodebaseUpdate,
    codebase: Codebase = Depends(get_verified_codebase),
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
):
    """Update a codebase."""

    update_data = codebase_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(codebase, field, value)

    updated_codebase = codebase_repo.update(codebase)
    codebase_repo.db.commit()
    codebase_repo.db.refresh(updated_codebase)
    return updated_codebase


@router.delete("/{codebase_id}", response_model=DeleteResponse)
async def delete_codebase(
    codebase_id: int,
    codebase: Codebase = Depends(get_verified_codebase),
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
):
    """Delete a codebase."""
    deleted = codebase_repo.delete_by_id(codebase_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Codebase not found")

    codebase_repo.db.commit()
    return {"message": "Codebase deleted successfully", "success": True}
