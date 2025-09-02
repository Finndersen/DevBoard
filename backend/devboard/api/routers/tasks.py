"""Task API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.db.database import get_db
from devboard.db.models import Task
from devboard.db.repositories import ContextProviderResourceRepository, TaskRepository
from devboard.schemas.configuration import ResourceResponse, TaskResourceCreate
from devboard.schemas.task import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter()


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(project_id: int = None, db: Session = Depends(get_db)):
    """List tasks, optionally filtered by project."""
    task_repo = TaskRepository(db)
    tasks = task_repo.get_all(project_id=project_id)
    return tasks


@router.post("/", response_model=TaskResponse)
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    """Create a new task."""
    task_repo = TaskRepository(db)
    db_task = Task(**task.model_dump())
    created_task = task_repo.create(db_task)
    db.commit()
    db.refresh(created_task)
    return created_task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """Get a specific task."""
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)):
    """Update a task."""
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    updated_task = task_repo.update(task)
    db.commit()
    db.refresh(updated_task)
    return updated_task


@router.delete("/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Delete a task."""
    task_repo = TaskRepository(db)
    deleted = task_repo.delete_by_id(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    db.commit()
    return {"message": "Task deleted successfully"}


# Task Resource Endpoints


@router.get("/{task_id}/resources", response_model=list[ResourceResponse])
async def list_task_resources(task_id: int, db: Session = Depends(get_db)):
    """Get all context provider resources for a task."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    resource_repo = ContextProviderResourceRepository(db)
    resources = resource_repo.get_resources_for_task(task_id)
    return resources


@router.post("/{task_id}/resources", response_model=ResourceResponse)
async def create_task_resource(
    task_id: int, resource: TaskResourceCreate, db: Session = Depends(get_db)
):
    """Add a context provider resource to a task."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    resource_repo = ContextProviderResourceRepository(db)
    created_resource = resource_repo.create_task_resource(
        task_id=task_id, resource_uri=resource.resource_uri, description=resource.description
    )

    db.commit()
    db.refresh(created_resource)
    return created_resource


@router.delete("/{task_id}/resources/{resource_id}")
async def delete_task_resource(task_id: int, resource_id: int, db: Session = Depends(get_db)):
    """Remove a context provider resource from a task."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    resource_repo = ContextProviderResourceRepository(db)
    deleted = resource_repo.delete_task_resource(task_id, resource_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail="Resource not found or does not belong to this task"
        )

    db.commit()
    return {"message": "Resource deleted successfully"}
