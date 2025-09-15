"""Project API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.agents import get_project_agent_conversation_service
from devboard.api.dependencies.entities import get_verified_project
from devboard.api.dependencies.repositories import (
    get_document_repository,
    get_project_conversation_message_repository,
    get_project_repository,
    get_task_repository,
)
from devboard.api.dependencies.services import (
    get_context_assembly_service,
    get_resource_service,
)
from devboard.api.schemas import (
    DeleteResponse,
    ProjectCreate,
    ProjectResourceCreate,
    ProjectResponse,
    ProjectUpdate,
    ResourceResponse,
    TaskCreate,
    TaskResponse,
)
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    ConversationMessage,
    MessageRole,
    PromptResponse,
    ToolApprovalRequest,
)
from devboard.context_providers import ContextProviderUnavailable
from devboard.db.models.messages import MessageType
from devboard.db.models.project import Project
from devboard.db.repositories import (
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.db.repositories.conversation_message import (
    ProjectConversationMessageRepository,
)
from devboard.services.agent_conversation import AgentConversationService
from devboard.services.context_assembly import (
    ContextAssemblyService,
    NoProviderFound,
)
from devboard.services.resource_service import (
    ResourceService,
    UnsupportedResourceUriError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """List all projects."""
    projects = project_repo.get_all()
    return projects


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """Create a new project."""
    created_project = project_repo.create(name=project.name, description=project.description)
    return created_project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    project: Project = Depends(get_verified_project),
):
    """Get a specific project."""
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    project: Project = Depends(get_verified_project),
    document_repo: DocumentRepository = Depends(get_document_repository),
):
    """Update a project and its specification content."""
    update_data = project_update.model_dump(exclude_unset=True)

    # Handle specification content update separately
    specification = update_data.pop("specification", None)
    if specification is not None:
        # Update the specification document content
        document_repo.update_content(project.specification, specification)

    # Update other project fields
    for field, value in update_data.items():
        setattr(project, field, value)

    return project


@router.delete("/{project_id}", response_model=DeleteResponse)
async def delete_project(
    project_id: int,
    project: Project = Depends(get_verified_project),
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """Delete a project."""
    deleted = project_repo.delete_by_id(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    project_repo.db.commit()
    return {"message": "Project deleted successfully", "success": True}


# Project Task Endpoints
@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: int,
    project: Project = Depends(get_verified_project),
    task_repo: TaskRepository = Depends(get_task_repository),
):
    """List all tasks for a project."""
    tasks = task_repo.get_for_project(project_id)
    return tasks


@router.post("/{project_id}/tasks", response_model=TaskResponse)
async def create_project_task(
    project_id: int,
    task: TaskCreate,
    project: Project = Depends(get_verified_project),
    task_repo: TaskRepository = Depends(get_task_repository),
):
    """Create a new task for a specific project."""
    # Ensure the task is being created for the correct project
    if task.project_id != project_id:
        raise HTTPException(status_code=400, detail="Task project_id must match URL project_id")

    # Create task using repository
    created_task = task_repo.create(
        project_id=task.project_id,
        title=task.title,
        status=task.status,
        codebase_id=task.codebase_id,
        remote_task_id=task.remote_task_id,
    )
    task_repo.db.commit()
    task_repo.db.refresh(created_task)
    return created_task


# Project Resource Endpoints
@router.get("/{project_id}/resources", response_model=list[ResourceResponse])
async def list_project_resources(
    project_id: int,
    project: Project = Depends(get_verified_project),
    resource_service: ResourceService = Depends(get_resource_service),
):
    """Get all context provider resources for a project."""
    resources = resource_service.get_resources_for_project(project_id)
    return resources


@router.post("/{project_id}/resources", response_model=ResourceResponse)
async def create_project_resource(
    project_id: int,
    resource: ProjectResourceCreate,
    project: Project = Depends(get_verified_project),
    resource_service: ResourceService = Depends(get_resource_service),
):
    """Add a context provider resource to a project."""

    try:
        created_resource = await resource_service.create_project_resource(
            project_id=project_id,
            resource_uri=resource.resource_uri,
            description=resource.description,
        )
        resource_service.repository.db.commit()
        resource_service.repository.db.refresh(created_resource)
        return created_resource
    except UnsupportedResourceUriError as e:
        resource_service.repository.db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/{project_id}/resources/{resource_id}", response_model=DeleteResponse)
async def delete_project_resource(
    project_id: int,
    resource_id: int,
    project: Project = Depends(get_verified_project),
    resource_service: ResourceService = Depends(get_resource_service),
):
    """Remove a context provider resource from a project."""

    deleted = resource_service.delete_project_resource(project_id, resource_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Resource not found or does not belong to this project",
        )

    resource_service.repository.db.commit()
    return {"message": "Resource deleted successfully", "success": True}


@router.get("/{project_id}/agent/messages", response_model=list[ConversationMessage])
def list_project_agent_messages(
    project_id: int,
    project: Project = Depends(get_verified_project),
    message_repo: ProjectConversationMessageRepository = Depends(get_project_conversation_message_repository),
) -> list[ConversationMessage]:
    """List all conversation messages for a project's agent.

    Args:
        project_id: The project to get messages for
        project: Project instance
        message_repo: Message repository

    Returns:
        List of conversation messages
    """

    messages = message_repo.get_all_for_entity(entity_id=project_id, exclude_tool_calls=True)

    return [
        ConversationMessage(
            id=msg.id,
            role=MessageRole.USER if msg.message_type == MessageType.USER_PROMPT else MessageRole.AGENT,
            text_content=msg.text_content,
            timestamp=msg.timestamp,
        )
        for msg in messages
    ]


@router.post("/{project_id}/agent/messages", response_model=PromptResponse)
async def send_project_agent_message(
    project_id: int,
    request: ChatRequest,
    project: Project = Depends(get_verified_project),
    project_conversation_service: AgentConversationService = Depends(get_project_agent_conversation_service),
) -> PromptResponse:
    """Chat with the project agent.

    This endpoint allows users to ask questions about their project and get
    AI-powered responses based on context from GitHub, Jira, Slack, and codebase.

    Args:
        project_id: The project to query
        request: The chat request with user query
        project: Project instance
        project_conversation_service: Agent conversation service

    Returns:
        AI-generated response based on project context
    """

    # Process query with Q&A agent
    response = await project_conversation_service.send_message(message=request.message, entity_id=project_id)

    return response


@router.post("/{project_id}/agent/approve-tools", response_model=PromptResponse)
async def approve_project_agent_tools(
    project_id: int,
    request: ToolApprovalRequest,
    project: Project = Depends(get_verified_project),
    project_conversation_service: AgentConversationService = Depends(get_project_agent_conversation_service),
) -> PromptResponse:
    """Approve or deny tools for the project agent.

    This endpoint allows users to approve or deny tool calls from the project agent
    and continue the conversation based on the approval decisions.

    Args:
        project_id: The project to query
        request: The tool approval request
        project: Project instance
        project_conversation_service: Agent conversation service

    Returns:
        AI-generated response based on tool approval decisions
    """
    # Process tool approvals
    response = await project_conversation_service.process_tool_approvals(
        approvals=request.approvals, entity_id=project_id
    )

    return response


@router.get("/{project_id}/context", response_model=dict[str, Any])
async def get_project_context(
    project_id: int,
    query: str = "general context",
    project: Project = Depends(get_verified_project),
    context_service: ContextAssemblyService = Depends(get_context_assembly_service),
) -> dict[str, Any]:
    """Get assembled context for a project.

    This endpoint shows what context is available for a project,
    useful for debugging and understanding what the Q&A agent has access to.

    Args:
        project_id: The project to get context for
        query: Sample query for context assembly (optional)
        project: Project instance
        context_service: Context assembly service

    Returns:
        Assembled context data including EAGER and ON_DEMAND resources
    """
    try:
        # Get context assembly
        context_data = await context_service.get_project_context(project_id, query)

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
async def validate_resource_uri(
    resource_uri: str,
    context_service: ContextAssemblyService = Depends(get_context_assembly_service),
) -> dict[str, Any]:
    """Validate a resource URI and get provider information.

    This endpoint helps users validate resource URIs before adding them
    to their projects as context provider resources.

    Args:
        resource_uri: The URI to validate
        context_service: Context assembly service

    Returns:
        Validation results and provider information
    """
    try:
        result = await context_service.get_resource_info(resource_uri)
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
