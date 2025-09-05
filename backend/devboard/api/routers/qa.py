"""Q&A agent API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from devboard.context_providers import ContextProviderUnavailable
from devboard.db.database import get_db
from devboard.db.repositories import ProjectRepository
from devboard.services.context_assembly import NoProviderFound
from devboard.services.qa_agent import qa_agent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["qa"])


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
