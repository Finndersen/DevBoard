"""Codebase API endpoints."""

from pathlib import Path

import logfire
from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.entities import get_verified_codebase
from devboard.api.dependencies.repositories import get_codebase_repository, get_worktree_slot_repository
from devboard.api.schemas import (
    BootstrapCodebaseRequest,
    BootstrapCodebaseResponse,
    BootstrapPreviewRequest,
    BootstrapPreviewResponse,
    CodebaseCreate,
    CodebaseResponse,
    CodebaseUpdate,
    DeleteResponse,
    FilePreviewResponse,
    ValidatePathRequest,
    ValidatePathResponse,
)
from devboard.db.models import BranchHandling, Codebase, MergeMethod
from devboard.db.repositories import CodebaseRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.services.codebase_bootstrap_service import (
    BootstrapRequest,
    CodebaseBootstrapService,
)

router = APIRouter()


def get_bootstrap_service() -> CodebaseBootstrapService:
    """Dependency to get bootstrap service instance."""
    return CodebaseBootstrapService()


@router.get("/", response_model=list[CodebaseResponse])
async def list_codebases(
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
):
    """List all codebases."""
    codebases = codebase_repo.get_all()
    return codebases


@router.post("/validate-path", response_model=ValidatePathResponse)
async def validate_codebase_path(
    request: ValidatePathRequest,
    bootstrap_service: CodebaseBootstrapService = Depends(get_bootstrap_service),
):
    """Validate a directory path and check if bootstrap is needed.

    This endpoint checks if a directory exists, has git initialized,
    has commits, and whether it needs to be bootstrapped before
    adding as a codebase.
    """
    result = await bootstrap_service.validate_directory(request.path)
    return ValidatePathResponse(
        exists=result.exists,
        is_directory=result.is_directory,
        has_git=result.has_git,
        has_commits=result.has_commits,
        has_remote=result.has_remote,
        remote_url=result.remote_url,
        current_branch=result.current_branch,
        needs_bootstrap=result.needs_bootstrap,
        detected_project_type=result.detected_project_type,
    )


@router.post("/bootstrap/preview", response_model=BootstrapPreviewResponse)
async def preview_bootstrap(
    request: BootstrapPreviewRequest,
    bootstrap_service: CodebaseBootstrapService = Depends(get_bootstrap_service),
):
    """Preview files that will be created during bootstrap.

    Returns a list of files with their content that would be created
    if the bootstrap is executed.
    """
    previews = await bootstrap_service.preview_bootstrap(
        path=request.path,
        name=request.name,
        description=request.description,
        create_gitignore=request.create_gitignore,
        create_readme=request.create_readme,
        create_claude_md=request.create_claude_md,
    )

    return BootstrapPreviewResponse(
        files=[
            FilePreviewResponse(
                path=p.path,
                content=p.content,
                file_type=p.file_type,
            )
            for p in previews
        ]
    )


@router.post("/bootstrap", response_model=BootstrapCodebaseResponse)
async def bootstrap_codebase(
    request: BootstrapCodebaseRequest,
    bootstrap_service: CodebaseBootstrapService = Depends(get_bootstrap_service),
):
    """Bootstrap a directory with git init and starter files.

    This initializes a git repository, creates optional starter files
    (.gitignore, README.md, CLAUDE.md), creates an initial commit,
    and optionally configures and pushes to a remote.
    """
    bootstrap_request = BootstrapRequest(
        path=request.path,
        name=request.name,
        description=request.description,
        create_gitignore=request.create_gitignore,
        create_readme=request.create_readme,
        create_claude_md=request.create_claude_md,
        branch_name=request.branch_name,
        initial_commit_message=request.initial_commit_message,
        remote_url=request.remote_url,
        push_to_remote=request.push_to_remote,
    )

    result = await bootstrap_service.execute_bootstrap(bootstrap_request)

    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error_message or "Bootstrap failed",
        )

    return BootstrapCodebaseResponse(
        success=result.success,
        commit_hash=result.commit_hash,
        files_created=result.files_created,
        error_message=result.error_message,
    )


@router.post("/", response_model=CodebaseResponse)
async def create_codebase(
    codebase: CodebaseCreate,
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
):
    """Create a new codebase."""
    logfire.info(f"[DEBUG] create_codebase called with: {codebase.model_dump()}")

    # Validate that the local path exists and is a directory
    path = Path(codebase.local_path).resolve()
    logfire.info(f"[DEBUG] Resolved path: {path}")

    if not path.exists():
        logfire.error(f"[DEBUG] Path does not exist: {path}")
        raise HTTPException(status_code=400, detail=f"Local path does not exist: {codebase.local_path}")

    if not path.is_dir():
        logfire.error(f"[DEBUG] Path is not a directory: {path}")
        raise HTTPException(
            status_code=400,
            detail=f"Local path is not a directory: {codebase.local_path}",
        )

    # Auto-detect git remote URL if the directory is a git repository
    logfire.info(f"[DEBUG] Creating GitRepoIntegration for: {codebase.local_path}")
    git = GitRepoIntegration(codebase.local_path)

    try:
        repository_url = await git.detect_git_remote_url()
        logfire.info(f"[DEBUG] Detected repository_url: {repository_url}")
    except Exception as e:
        logfire.error(f"[DEBUG] Error detecting git remote URL: {e}")
        raise

    # Validate repository has at least one commit
    try:
        has_commits = await git.has_commits()
        logfire.info(f"[DEBUG] has_commits: {has_commits}")
        if not has_commits:
            logfire.error("[DEBUG] Repository has no commits")
            raise HTTPException(
                status_code=400,
                detail="Repository has no commits. Please make at least one commit before adding as a codebase.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"[DEBUG] Error checking commits: {e}")
        raise

    # Auto-detect default branch if not provided
    default_branch = codebase.default_branch
    if not default_branch:
        try:
            default_branch = await git.get_default_branch()
            logfire.info(f"[DEBUG] Detected default_branch: {default_branch}")
        except Exception as e:
            logfire.error(f"[DEBUG] Error detecting default branch: {e}")
            raise

    # Determine merge_method: use provided value, or default to SQUASH
    merge_method = codebase.merge_method
    if merge_method is None:
        merge_method = MergeMethod.SQUASH
    logfire.info(f"[DEBUG] merge_method: {merge_method}")

    # Determine branch_handling: use provided value, or auto-detect based on remote URL
    branch_handling = codebase.branch_handling
    if branch_handling is None:
        # Default to GITHUB_PR if remote URL exists, otherwise LOCAL_MERGE
        branch_handling = BranchHandling.GITHUB_PR if repository_url else BranchHandling.LOCAL_MERGE
    logfire.info(f"[DEBUG] branch_handling: {branch_handling}")

    # Validate github_pr branch handling requires a remote URL
    if branch_handling == BranchHandling.GITHUB_PR and not repository_url:
        logfire.error("[DEBUG] GitHub PR branch handling requires remote URL")
        raise HTTPException(
            status_code=400,
            detail="GitHub PR branch handling requires a repository with a remote URL configured",
        )

    # Create the codebase with auto-detected values
    codebase_data = codebase.model_dump()
    codebase_data["repository_url"] = repository_url
    codebase_data["default_branch"] = default_branch
    codebase_data["merge_method"] = merge_method.value
    codebase_data["branch_handling"] = branch_handling.value
    logfire.info(f"[DEBUG] Final codebase_data: {codebase_data}")

    try:
        db_codebase = Codebase(**codebase_data)
        logfire.info(f"[DEBUG] Created Codebase model: {db_codebase}")
        created_codebase = codebase_repo.create(db_codebase)
        logfire.info(f"[DEBUG] Created codebase in repo, id: {created_codebase.id}")
        codebase_repo.db.commit()
        logfire.info("[DEBUG] Committed to database")
        codebase_repo.db.refresh(created_codebase)
        logfire.info("[DEBUG] Refreshed codebase from database")
    except Exception as e:
        logfire.error(f"[DEBUG] Error creating codebase in database: {e}")
        raise

    # Bootstrap main repo slot for this codebase
    try:
        worktree_slot_repo.create(
            codebase_id=created_codebase.id,
            path=created_codebase.local_path,
            is_main_repo=True,
        )
        logfire.info("[DEBUG] Created main repo worktree slot")
    except Exception as e:
        logfire.error(f"[DEBUG] Error creating worktree slot: {e}")
        raise

    logfire.info(f"[DEBUG] Returning created_codebase: {created_codebase.id}")
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
