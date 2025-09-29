"""Codebase API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.entities import get_verified_codebase
from devboard.api.dependencies.repositories import get_codebase_repository
from devboard.api.dependencies.services import get_codebase_investigation_service
from devboard.api.schemas import (
    CodebaseCreate,
    CodebaseResponse,
    CodebaseUpdate,
    DeleteResponse,
)
from devboard.api.schemas.codebase import (
    ArchitectureDocumentResponse,
    ArchitectureGenerationResponse,
    ArchitectureUpdateRequest,
    ArchitectureUpdateResponse,
)
from devboard.db.models import Codebase
from devboard.db.repositories import CodebaseRepository
from devboard.integrations.codebase import detect_git_remote_url
from devboard.services.codebase_investigation import CodebaseInvestigationService

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
    repository_url = detect_git_remote_url(codebase.local_path)

    # Create the codebase with auto-detected repository URL
    codebase_data = codebase.model_dump()
    codebase_data["repository_url"] = repository_url

    db_codebase = Codebase(**codebase_data)
    created_codebase = codebase_repo.create(db_codebase)
    codebase_repo.db.commit()
    codebase_repo.db.refresh(created_codebase)
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


# Architecture document endpoints


# New combined endpoint
@router.get("/{codebase_id}/architecture_document/", response_model=ArchitectureDocumentResponse)
async def get_architecture_document(
    codebase_id: int,
    codebase: Codebase = Depends(get_verified_codebase),
    investigation_service: CodebaseInvestigationService = Depends(get_codebase_investigation_service),
):
    """Get complete architecture document information including content and hash."""

    # Get complete architecture document
    document = investigation_service.get_architecture_document(codebase.local_path)

    return ArchitectureDocumentResponse(
        exists=document.exists,
        content=document.content,
        content_hash=document.content_hash,
        file_path=str(document.file_path) if document.file_path else None,
        size_bytes=document.size_bytes,
    )


# New update endpoint
@router.put("/{codebase_id}/architecture_document/", response_model=ArchitectureUpdateResponse)
async def update_architecture_document(
    codebase_id: int,
    request: ArchitectureUpdateRequest,
    codebase: Codebase = Depends(get_verified_codebase),
    investigation_service: CodebaseInvestigationService = Depends(get_codebase_investigation_service),
):
    """Update architecture document with conflict detection."""

    # Update architecture document
    result = investigation_service.update_architecture_content(
        codebase_path=codebase.local_path,
        new_content=request.content,
        original_hash=request.original_hash,
    )

    # Handle conflict as 409 status
    if not result.success and result.error_type == "conflict":
        raise HTTPException(
            status_code=409,
            detail={
                "success": False,
                "message": result.message,
                "error_type": result.error_type,
                "current_hash": result.current_hash,
            },
        )

    # Handle other errors as 400
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": result.message,
                "error_type": result.error_type,
            },
        )

    return ArchitectureUpdateResponse(success=result.success, content_hash=result.content_hash, message=result.message)


@router.post(
    "/{codebase_id}/architecture_document/generate",
    response_model=ArchitectureGenerationResponse,
)
async def generate_architecture_document(
    codebase_id: int,
    codebase: Codebase = Depends(get_verified_codebase),
    investigation_service: CodebaseInvestigationService = Depends(get_codebase_investigation_service),
):
    """Generate or update architecture document for a codebase using AI."""

    # Generate architecture document
    result = await investigation_service.generate_architecture_document(
        codebase_path=codebase.local_path,
        codebase_name=codebase.name,
    )

    return ArchitectureGenerationResponse(
        success=result.success,
        file_path=str(result.file_path) if result.file_path else None,
        content=result.content,
        error_message=result.error_message,
        error_type=result.error_type,
    )
