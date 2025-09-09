"""Project API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from devboard.agents.project_agent import qa_agent_service
from devboard.api.schemas import (
    DeleteResponse,
    ProjectCreate,
    ProjectResourceCreate,
    ProjectResponse,
    ProjectUpdate,
    ResourceResponse,
    TaskResponse,
)
from devboard.context_providers import ContextProviderUnavailable
from devboard.db.database import get_db
from devboard.db.models import Project
from devboard.db.repositories import ProjectRepository, TaskRepository
from devboard.services.context_assembly import NoProviderFound
from devboard.services.resource_service import ResourceService, UnsupportedResourceUriError

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


@router.delete("/{project_id}", response_model=DeleteResponse)
async def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project."""
    project_repo = ProjectRepository(db)
    deleted = project_repo.delete_by_id(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    db.commit()
    return {"message": "Project deleted successfully", "success": True}


# Project Task Endpoints
@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
async def list_project_tasks(project_id: int, db: Session = Depends(get_db)):
    """List all tasks for a project."""
    # Verify project exists
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task_repo = TaskRepository(db)
    tasks = task_repo.get_for_project(project_id)
    return tasks


# Project Resource Endpoints


@router.get("/{project_id}/resources", response_model=list[ResourceResponse])
async def list_project_resources(project_id: int, db: Session = Depends(get_db)):
    """Get all context provider resources for a project."""
    # Verify project exists
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    resource_service = ResourceService(db)
    resources = resource_service.get_resources_for_project(project_id)
    return resources


@router.post("/{project_id}/resources", response_model=ResourceResponse)
async def create_project_resource(
    project_id: int, resource: ProjectResourceCreate, db: Session = Depends(get_db)
):
    """Add a context provider resource to a project."""
    # Verify project exists
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    resource_service = ResourceService(db)
    try:
        created_resource = await resource_service.create_project_resource(
            project_id=project_id,
            resource_uri=resource.resource_uri,
            description=resource.description,
        )
        db.commit()
        db.refresh(created_resource)
        return created_resource
    except UnsupportedResourceUriError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/{project_id}/resources/{resource_id}", response_model=DeleteResponse)
async def delete_project_resource(project_id: int, resource_id: int, db: Session = Depends(get_db)):
    """Remove a context provider resource from a project."""
    # Verify project exists
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    resource_service = ResourceService(db)
    deleted = resource_service.delete_project_resource(project_id, resource_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail="Resource not found or does not belong to this project"
        )

    db.commit()
    return {"message": "Resource deleted successfully", "success": True}


class ChatRequest(BaseModel):
    """Request model for project chat."""

    query: str


class ChatResponse(BaseModel):
    """Response model for project chat."""

    response: str
    project_id: int


@router.post("/{project_id}/chat", response_model=ChatResponse)
async def chat_with_project(
    project_id: int, request: ChatRequest, db: Session = Depends(get_db)
) -> ChatResponse:
    """Chat with the project Q&A agent.

    This endpoint allows users to ask questions about their project and get
    AI-powered responses based on context from GitHub, Jira, Slack, and codebase.

    Args:
        project_id: The project to query
        request: The chat request with user query
        db: Database session

    Returns:
        AI-generated response based on project context
    """
    try:
        # Verify project exists
        project_repo = ProjectRepository(db)
        project = project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Process query with Q&A agent
        response = await qa_agent_service.chat(project_id, request.query)

        return ChatResponse(response=response, project_id=project_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in project chat for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {e}") from e


@router.get("/{project_id}/context", response_model=dict[str, Any])
async def get_project_context(
    project_id: int, query: str = "general context", db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Get assembled context for a project.

    This endpoint shows what context is available for a project,
    useful for debugging and understanding what the Q&A agent has access to.

    Args:
        project_id: The project to get context for
        query: Sample query for context assembly (optional)
        db: Database session

    Returns:
        Assembled context data including EAGER and ON_DEMAND resources
    """
    try:
        # Verify project exists
        project_repo = ProjectRepository(db)
        project = project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get context assembly
        context_data = await qa_agent_service.context_service.get_project_context(project_id, query)

        return {
            "project_id": project_id,
            "project_name": project.name,
            "query": query,
            "eager_context": [
                {
                    "uri": ctx.uri,
                    "user_description": ctx.description,
                    "provider_type": ctx.provider_type,
                    "data": ctx.data,
                }
                for ctx in context_data.eager_context
            ],
            "on_demand_resources": [
                {
                    "uri": res.uri,
                    "description": res.description,
                    "provider_type": res.provider_type,
                    "has_user_description": res.has_user_description,
                }
                for res in context_data.on_demand_resources
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting context for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Context assembly failed: {e}") from e


@router.post("/validate-resource", response_model=dict[str, Any])
async def validate_resource_uri(resource_uri: str) -> dict[str, Any]:
    """Validate a resource URI and get provider information.

    This endpoint helps users validate resource URIs before adding them
    to their projects as context provider resources.

    Args:
        resource_uri: The URI to validate

    Returns:
        Validation results and provider information
    """
    try:
        result = await qa_agent_service.context_service.get_resource_info(resource_uri)
        return {
            "resource_uri": resource_uri,
            "valid": True,
            "provider_type": result.provider.provider_type,
            "strategy": result.retrieval_strategy.value,
            "description": result.description,
            "error": None,
        }
    except (NoProviderFound, ContextProviderUnavailable) as e:
        return {
            "resource_uri": resource_uri,
            "valid": False,
            "provider_type": None,
            "strategy": None,
            "description": None,
            "error": str(e),
        }
