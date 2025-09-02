"""Codebase API endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.db.database import get_db
from devboard.db.models import Codebase
from devboard.db.repositories import CodebaseRepository
from devboard.integrations.filesystem import detect_git_remote_url
from devboard.schemas.codebase import CodebaseCreate, CodebaseResponse, CodebaseUpdate

router = APIRouter()


@router.get("/", response_model=list[CodebaseResponse])
async def list_codebases(db: Session = Depends(get_db)):
    """List all codebases."""
    codebase_repo = CodebaseRepository(db)
    codebases = codebase_repo.get_all()
    return codebases


@router.post("/", response_model=CodebaseResponse)
async def create_codebase(codebase: CodebaseCreate, db: Session = Depends(get_db)):
    """Create a new codebase."""
    # Validate that the local path exists and is a directory
    path = Path(codebase.local_path).resolve()
    if not path.exists():
        raise HTTPException(
            status_code=400, detail=f"Local path does not exist: {codebase.local_path}"
        )

    if not path.is_dir():
        raise HTTPException(
            status_code=400, detail=f"Local path is not a directory: {codebase.local_path}"
        )

    # Auto-detect git remote URL if the directory is a git repository
    repository_url = detect_git_remote_url(codebase.local_path)

    # Create the codebase with auto-detected repository URL
    codebase_data = codebase.model_dump()
    codebase_data["repository_url"] = repository_url

    codebase_repo = CodebaseRepository(db)
    db_codebase = Codebase(**codebase_data)
    created_codebase = codebase_repo.create(db_codebase)
    db.commit()
    db.refresh(created_codebase)
    return created_codebase


@router.get("/{codebase_id}", response_model=CodebaseResponse)
async def get_codebase(codebase_id: int, db: Session = Depends(get_db)):
    """Get a specific codebase."""
    codebase_repo = CodebaseRepository(db)
    codebase = codebase_repo.get_by_id(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")
    return codebase


@router.patch("/{codebase_id}", response_model=CodebaseResponse)
async def update_codebase(
    codebase_id: int, codebase_update: CodebaseUpdate, db: Session = Depends(get_db)
):
    """Update a codebase."""
    codebase_repo = CodebaseRepository(db)
    codebase = codebase_repo.get_by_id(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    update_data = codebase_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(codebase, field, value)

    updated_codebase = codebase_repo.update(codebase)
    db.commit()
    db.refresh(updated_codebase)
    return updated_codebase


@router.delete("/{codebase_id}")
async def delete_codebase(codebase_id: int, db: Session = Depends(get_db)):
    """Delete a codebase."""
    codebase_repo = CodebaseRepository(db)
    deleted = codebase_repo.delete_by_id(codebase_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Codebase not found")

    db.commit()
    return {"message": "Codebase deleted successfully"}
