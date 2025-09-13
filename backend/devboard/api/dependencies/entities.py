from fastapi import Depends, HTTPException

from devboard.api.dependencies.repositories import (
    get_codebase_repository,
    get_project_repository,
    get_task_repository,
)
from devboard.db.models import Codebase, Project, Task
from devboard.db.repositories import (
    CodebaseRepository,
    ProjectRepository,
    TaskRepository,
)


def get_verified_project(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repository),
) -> Project:
    """Get a project by ID, raising 404 if not found."""
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_verified_task(
    task_id: int,
    task_repo: TaskRepository = Depends(get_task_repository),
) -> Task:
    """Get a task by ID, raising 404 if not found."""
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def get_verified_codebase(
    codebase_id: int,
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
) -> Codebase:
    """Get a codebase by ID, raising 404 if not found."""
    codebase = codebase_repo.get_by_id(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")
    return codebase
