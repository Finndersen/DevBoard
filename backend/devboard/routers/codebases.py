"""Codebase API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.db.database import get_db
from devboard.db.models import Codebase
from devboard.schemas.codebase import CodebaseCreate, CodebaseResponse, CodebaseUpdate

router = APIRouter()


@router.get("/", response_model=list[CodebaseResponse])
async def list_codebases(db: Session = Depends(get_db)):
    """List all codebases."""
    codebases = db.query(Codebase).all()
    return codebases


@router.post("/", response_model=CodebaseResponse)
async def create_codebase(codebase: CodebaseCreate, db: Session = Depends(get_db)):
    """Create a new codebase."""
    db_codebase = Codebase(**codebase.model_dump())
    db.add(db_codebase)
    db.commit()
    db.refresh(db_codebase)
    return db_codebase


@router.get("/{codebase_id}", response_model=CodebaseResponse)
async def get_codebase(codebase_id: int, db: Session = Depends(get_db)):
    """Get a specific codebase."""
    codebase = db.query(Codebase).filter(Codebase.id == codebase_id).first()
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")
    return codebase


@router.patch("/{codebase_id}", response_model=CodebaseResponse)
async def update_codebase(
    codebase_id: int, codebase_update: CodebaseUpdate, db: Session = Depends(get_db)
):
    """Update a codebase."""
    codebase = db.query(Codebase).filter(Codebase.id == codebase_id).first()
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    update_data = codebase_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(codebase, field, value)

    db.commit()
    db.refresh(codebase)
    return codebase


@router.delete("/{codebase_id}")
async def delete_codebase(codebase_id: int, db: Session = Depends(get_db)):
    """Delete a codebase."""
    codebase = db.query(Codebase).filter(Codebase.id == codebase_id).first()
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    db.delete(codebase)
    db.commit()
    return {"message": "Codebase deleted successfully"}
