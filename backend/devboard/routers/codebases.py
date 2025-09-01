"""Codebase API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.db.database import get_db
from devboard.db.models import Codebase
from devboard.repositories.codebase import CodebaseRepository
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
    codebase_repo = CodebaseRepository(db)
    db_codebase = Codebase(**codebase.model_dump())
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
