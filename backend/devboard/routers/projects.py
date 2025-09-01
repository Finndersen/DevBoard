"""Project API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.db.database import get_db
from devboard.db.models import Project
from devboard.repositories.project import ProjectRepository
from devboard.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter()


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(db: Session = Depends(get_db)):
    """List all projects."""
    project_repo = ProjectRepository(db)
    projects = project_repo.get_all()
    return projects


@router.post("/", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project."""
    project_repo = ProjectRepository(db)
    db_project = Project(**project.model_dump())
    created_project = project_repo.create(db_project)
    db.commit()
    db.refresh(created_project)
    return created_project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get a specific project."""
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int, project_update: ProjectUpdate, db: Session = Depends(get_db)
):
    """Update a project."""
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    updated_project = project_repo.update(project)
    db.commit()
    db.refresh(updated_project)
    return updated_project


@router.delete("/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project."""
    project_repo = ProjectRepository(db)
    deleted = project_repo.delete_by_id(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    db.commit()
    return {"message": "Project deleted successfully"}
