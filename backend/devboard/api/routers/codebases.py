"""Codebase API endpoints."""

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.entities import get_verified_codebase
from devboard.api.dependencies.repositories import get_codebase_repository, get_worktree_slot_repository
from devboard.api.schemas import (
    CodebaseClone,
    CodebaseCommonOptions,
    CodebaseCreate,
    CodebaseInit,
    CodebaseResponse,
    CodebaseUpdate,
    DeleteResponse,
)
from devboard.db.models import BranchHandling, Codebase, MergeMethod
from devboard.db.repositories import CodebaseRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import ShellCommandExecutionError

router = APIRouter()


async def _finalize_codebase_creation(
    *,
    local_path: str,
    name: str,
    options: CodebaseCommonOptions,
    validate_commits: bool = True,
    git: GitRepoIntegration,
    codebase_repo: CodebaseRepository,
    worktree_slot_repo: WorktreeSlotRepository,
) -> Codebase:
    """Shared post-creation logic: detect remote, validate, resolve defaults, persist."""
    repository_url = await git.detect_git_remote_url()

    if validate_commits and not await git.has_commits():
        raise HTTPException(
            status_code=400,
            detail="Repository has no commits. Please make at least one commit before adding as a codebase.",
        )

    default_branch = options.default_branch or await git.get_default_branch()
    merge_method = options.merge_method or MergeMethod.SQUASH
    branch_handling = options.branch_handling or (
        BranchHandling.GITHUB_PR if repository_url else BranchHandling.DIRECT_MERGE
    )

    if branch_handling == BranchHandling.GITHUB_PR and not repository_url:
        raise HTTPException(
            status_code=400,
            detail="GitHub PR branch handling requires a repository with a remote URL configured",
        )

    db_codebase = Codebase(
        name=name,
        description=options.description or "",
        local_path=local_path,
        repository_url=repository_url,
        default_branch=default_branch,
        merge_method=merge_method.value,
        branch_handling=branch_handling.value,
        max_worktrees=options.max_worktrees,
        setup_command=options.setup_command,
        developer_context=options.developer_context,
    )
    created_codebase = codebase_repo.create(db_codebase)
    codebase_repo.db.commit()
    codebase_repo.db.refresh(created_codebase)

    worktree_slot_repo.create(
        codebase_id=created_codebase.id,
        path=created_codebase.local_path,
        is_main_repo=True,
    )

    return created_codebase


def _derive_name_from_url(url: str) -> str:
    """Extract a codebase name from a git URL (last path segment, strip .git suffix)."""
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


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
    """Create a new codebase from an existing local directory."""
    path = Path(codebase.local_path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Local path does not exist: {codebase.local_path}")

    if not path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Local path is not a directory: {codebase.local_path}",
        )

    git = GitRepoIntegration(codebase.local_path)
    return await _finalize_codebase_creation(
        local_path=codebase.local_path,
        name=codebase.name,
        options=codebase,
        validate_commits=True,
        git=git,
        codebase_repo=codebase_repo,
        worktree_slot_repo=worktree_slot_repo,
    )


@router.post("/clone", response_model=CodebaseResponse)
async def clone_codebase(
    codebase: CodebaseClone,
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
):
    """Clone a remote git repository and register it as a codebase."""
    parent_dir = Path(codebase.parent_directory).expanduser().resolve()
    if not parent_dir.exists():
        raise HTTPException(status_code=400, detail=f"Parent directory does not exist: {codebase.parent_directory}")

    name = codebase.name or _derive_name_from_url(codebase.repository_url)
    if not name:
        raise HTTPException(
            status_code=400,
            detail="Could not derive a name from the repository URL — please provide one explicitly.",
        )

    target_path = parent_dir / name

    if target_path.exists():
        raise HTTPException(status_code=400, detail=f"Target directory already exists: {target_path}")

    try:
        git = await GitRepoIntegration.clone_repo(codebase.repository_url, target_path)
        return await _finalize_codebase_creation(
            local_path=str(target_path),
            name=name,
            options=codebase,
            validate_commits=False,
            git=git,
            codebase_repo=codebase_repo,
            worktree_slot_repo=worktree_slot_repo,
        )
    except ShellCommandExecutionError as e:
        shutil.rmtree(target_path, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Git clone failed: {e}") from e


@router.post("/init", response_model=CodebaseResponse)
async def init_codebase(
    codebase: CodebaseInit,
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
):
    """Initialise a new git project directory and register it as a codebase."""
    target_path = Path(codebase.directory).expanduser().resolve()

    if target_path.exists():
        raise HTTPException(status_code=400, detail=f"Target directory already exists: {target_path}")

    try:
        git = await GitRepoIntegration.init_repo(target_path)
        git.write_initial_project_files(codebase.name, codebase.description)
        await git.add_and_commit("Initial commit")
        return await _finalize_codebase_creation(
            local_path=str(target_path),
            name=codebase.name,
            options=codebase,
            validate_commits=False,
            git=git,
            codebase_repo=codebase_repo,
            worktree_slot_repo=worktree_slot_repo,
        )
    except ShellCommandExecutionError as e:
        shutil.rmtree(target_path, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Git operation failed: {e}") from e


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
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
):
    """Update a codebase."""
    update_data = codebase_update.model_dump(exclude_unset=True)

    # Determine the effective repository_url after update
    effective_repository_url = update_data.get("repository_url", codebase.repository_url)

    # Determine the effective branch_handling after update
    effective_branch_handling = update_data.get("branch_handling", codebase.branch_handling)
    if isinstance(effective_branch_handling, BranchHandling):
        effective_branch_handling = effective_branch_handling.value

    # Validate github_pr branch handling requires a remote URL
    if effective_branch_handling == BranchHandling.GITHUB_PR.value and not effective_repository_url:
        raise HTTPException(
            status_code=400,
            detail="GitHub PR branch handling requires a repository with a remote URL configured",
        )

    for field, value in update_data.items():
        setattr(codebase, field, value)

    updated_codebase = codebase_repo.update(codebase)

    # Sync main slot path when local_path changes
    if "local_path" in update_data:
        try:
            main_slot = worktree_slot_repo.get_main_slot_for_codebase(codebase_id)
            main_slot.path = update_data["local_path"]
            worktree_slot_repo.update(main_slot)
        except ValueError:
            pass

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
