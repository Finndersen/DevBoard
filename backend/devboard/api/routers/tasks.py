"""Task API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.agents import get_task_agent_conversation_service
from devboard.api.dependencies.entities import get_verified_task
from devboard.api.dependencies.repositories import (
    get_document_repository,
    get_project_repository,
    get_task_repository,
)
from devboard.api.dependencies.services import (
    get_resource_service,
)
from devboard.api.schemas import (
    DeleteResponse,
    ResourceResponse,
    StateTransitionRequest,
    TaskCreate,
    TaskResourceCreate,
    TaskResponse,
    TaskUpdate,
)
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    PromptResponse,
    ToolApprovalRequest,
)
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories import (
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.services.agent_conversation import AgentConversationService
from devboard.services.resource_service import (
    ResourceService,
    UnsupportedResourceUriError,
)

router = APIRouter()


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(
    project_id: int | None = None,
    task_repo: TaskRepository = Depends(get_task_repository),
):
    """List all tasks, optionally filtered by project."""
    if project_id:
        tasks = task_repo.get_for_project(project_id)
    else:
        tasks = task_repo.get_all()
    return tasks


@router.post("/", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    project_repo: ProjectRepository = Depends(get_project_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
):
    """Create a new task."""
    # Verify project exists
    project = project_repo.get_by_id(task.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, task: Task = Depends(get_verified_task)):
    """Get a specific task."""
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    task: Task = Depends(get_verified_task),
    task_repo: TaskRepository = Depends(get_task_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
):
    """Update a task and its document content."""

    update_data = task_update.model_dump(exclude_unset=True)

    # Handle specification content update separately
    specification = update_data.pop("specification", None)
    if specification is not None:
        # Update the specification document content
        document_repo.update_content(task.specification, specification)

    # Handle implementation plan content update separately
    implementation_plan = update_data.pop("implementation_plan", None)
    if implementation_plan is not None:
        # Create or update implementation plan document
        task_repo.set_task_implementation_plan(task, implementation_plan)

    # Update other task fields
    for field, value in update_data.items():
        setattr(task, field, value)

    updated_task = task_repo.update(task)
    task_repo.db.commit()
    task_repo.db.refresh(updated_task)
    return updated_task


@router.delete("/{task_id}", response_model=DeleteResponse)
async def delete_task(
    task_id: int,
    task: Task = Depends(get_verified_task),
    task_repo: TaskRepository = Depends(get_task_repository),
):
    """Delete a task."""
    deleted = task_repo.delete_by_id(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    task_repo.db.commit()
    return {"message": "Task deleted successfully", "success": True}


# Task Resource Endpoints


@router.get("/{task_id}/resources", response_model=list[ResourceResponse])
async def list_task_resources(
    task_id: int,
    task: Task = Depends(get_verified_task),
    resource_service: ResourceService = Depends(get_resource_service),
):
    """Get all context provider resources for a task."""

    resources = resource_service.get_resources_for_task(task_id)
    return resources


@router.post("/{task_id}/resources", response_model=ResourceResponse)
async def create_task_resource(
    task_id: int,
    resource: TaskResourceCreate,
    task: Task = Depends(get_verified_task),
    resource_service: ResourceService = Depends(get_resource_service),
):
    """Add a context provider resource to a task."""

    try:
        created_resource = await resource_service.create_task_resource(
            task_id=task_id,
            resource_uri=resource.resource_uri,
            description=resource.description,
        )
        resource_service.repository.db.commit()
        resource_service.repository.db.refresh(created_resource)
        return created_resource
    except UnsupportedResourceUriError as e:
        resource_service.repository.db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/{task_id}/resources/{resource_id}", response_model=DeleteResponse)
async def delete_task_resource(
    task_id: int,
    resource_id: int,
    task: Task = Depends(get_verified_task),
    resource_service: ResourceService = Depends(get_resource_service),
):
    """Remove a context provider resource from a task."""

    deleted = resource_service.delete_task_resource(task_id, resource_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resource not found or does not belong to this task")

    resource_service.repository.db.commit()
    return {"message": "Resource deleted successfully", "success": True}


# Task Planning Agent Endpoints
@router.post("/{task_id}/agent/messages", response_model=PromptResponse)
async def send_task_agent_message(
    task_id: int,
    request: ChatRequest,
    task_conversation_service: AgentConversationService = Depends(get_task_agent_conversation_service),
) -> PromptResponse:
    """Chat with the project agent.

    This endpoint allows users to ask questions about their project and get
    AI-powered responses based on context from GitHub, Jira, Slack, and codebase.

    Args:
        task_id: The project to query
        request: The chat request with user query
        task_conversation_service: Agent conversation service dependency

    Returns:
        AI-generated response based on project context
    """
    # Process query with Q&A agent
    response = await task_conversation_service.send_message(message=request.message, entity_id=task_id)

    return response


@router.post("/{task_id}/agent/approve-tools", response_model=PromptResponse)
async def approve_task_agent_tools(
    task_id: int,
    request: ToolApprovalRequest,
    task_conversation_service: AgentConversationService = Depends(get_task_agent_conversation_service),
):
    """Approve or deny tool calls from the task planning agent."""
    # Process query with Q&A agent
    response = await task_conversation_service.process_tool_approvals(approvals=request.approvals, entity_id=task_id)

    return response


@router.post("/{task_id}/state-transition", response_model=TaskResponse)
async def transition_task_state(
    task_id: int,
    request: StateTransitionRequest,
    task: Task = Depends(get_verified_task),
    task_repo: TaskRepository = Depends(get_task_repository),
):
    """Manually transition task to a new state."""

    if request.new_state not in TaskStatus:
        raise HTTPException(status_code=400, detail=f"Invalid state: {request.new_state}")

    # Update task status
    task.status = request.new_state
    updated_task = task_repo.update(task)
    task_repo.db.commit()
    task_repo.db.refresh(updated_task)
    return updated_task
