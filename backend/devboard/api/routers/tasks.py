"""Task API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.agents.task_agent import (
    TaskPlanningAgent,
    TaskSpecificationAgent,
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
from devboard.db.database import get_db
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import (
    DocumentRepository,
    ProjectRepository,
    TaskConversationMessageRepository,
    TaskRepository,
)
from devboard.services.agent_conversation import AgentConversationService
from devboard.services.resource_service import (
    ResourceService,
    UnsupportedResourceUriError,
)

router = APIRouter()


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(project_id: int | None = None, db: Session = Depends(get_db)):
    """List all tasks, optionally filtered by project."""
    task_repo = TaskRepository(db)
    if project_id:
        tasks = task_repo.get_for_project(project_id)
    else:
        tasks = task_repo.get_all()
    return tasks


@router.post("/", response_model=TaskResponse)
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    """Create a new task."""
    # Verify project exists
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(task.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Create task using repository
    task_repo = TaskRepository(db)
    created_task = task_repo.create(
        project_id=task.project_id,
        title=task.title,
        status=task.status,
        codebase_id=task.codebase_id,
        remote_task_id=task.remote_task_id,
    )
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
async def update_task(
    task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)
):
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


@router.delete("/{task_id}", response_model=DeleteResponse)
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Delete a task."""
    task_repo = TaskRepository(db)
    deleted = task_repo.delete_by_id(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    db.commit()
    return {"message": "Task deleted successfully", "success": True}


# Task Resource Endpoints


@router.get("/{task_id}/resources", response_model=list[ResourceResponse])
async def list_task_resources(task_id: int, db: Session = Depends(get_db)):
    """Get all context provider resources for a task."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    resource_service = ResourceService(db)
    resources = resource_service.get_resources_for_task(task_id)
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

    resource_service = ResourceService(db)
    try:
        created_resource = await resource_service.create_task_resource(
            task_id=task_id,
            resource_uri=resource.resource_uri,
            description=resource.description,
        )
        db.commit()
        db.refresh(created_resource)
        return created_resource
    except UnsupportedResourceUriError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/{task_id}/resources/{resource_id}", response_model=DeleteResponse)
async def delete_task_resource(
    task_id: int, resource_id: int, db: Session = Depends(get_db)
):
    """Remove a context provider resource from a task."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    resource_service = ResourceService(db)
    deleted = resource_service.delete_task_resource(task_id, resource_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail="Resource not found or does not belong to this task"
        )

    db.commit()
    return {"message": "Resource deleted successfully", "success": True}


# Task Planning Agent Endpoints
@router.post("/{task_id}/agent/messages", response_model=PromptResponse)
async def send_task_agent_message(
    task_id: int, request: ChatRequest, db: Session = Depends(get_db)
) -> PromptResponse:
    """Chat with the project agent.

    This endpoint allows users to ask questions about their project and get
    AI-powered responses based on context from GitHub, Jira, Slack, and codebase.

    Args:
        task_id: The project to query
        request: The chat request with user query
        db: Database session

    Returns:
        AI-generated response based on project context
    """
    try:
        # Verify task exists
        task_repo = TaskRepository(db)
        task = task_repo.get_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.status == TaskStatus.DEFINING:
            agent_type = TaskSpecificationAgent
        elif task.status == TaskStatus.PLANNING:
            agent_type = TaskPlanningAgent
        else:
            raise ValueError(
                f"Task in state {task.status} cannot accept agent messages"
            )

        agent = agent_type(task=task, document_repository=DocumentRepository(db))

        conversation_service = AgentConversationService(
            agent, message_repository=TaskConversationMessageRepository(db)
        )
        # Process query with Q&A agent
        response = await conversation_service.send_message(
            message=request.message, entity_id=task_id
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Chat processing failed: {e}"
        ) from e


@router.post("/{task_id}/agent/approve-tools", response_model=PromptResponse)
async def approve_task_agent_tools(
    task_id: int, request: ToolApprovalRequest, db: Session = Depends(get_db)
):
    """Approve or deny tool calls from the task planning agent."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == TaskStatus.DEFINING:
        agent_type = TaskSpecificationAgent
    elif task.status == TaskStatus.PLANNING:
        agent_type = TaskPlanningAgent
    else:
        raise ValueError(f"Task in state {task.status} cannot accept agent messages")

    agent = agent_type(task=task, document_repository=DocumentRepository(db))

    conversation_service = AgentConversationService(
        agent, message_repository=TaskConversationMessageRepository(db)
    )
    # Process query with Q&A agent
    response = await conversation_service.process_tool_approvals(
        approvals=request.approvals, entity_id=task_id
    )

    return response


@router.post("/{task_id}/state-transition", response_model=TaskResponse)
async def transition_task_state(
    task_id: int, request: StateTransitionRequest, db: Session = Depends(get_db)
):
    """Manually transition task to a new state."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if request.new_state not in TaskStatus:
        raise HTTPException(
            status_code=400, detail=f"Invalid state: {request.new_state}"
        )

    # Update task status
    task.status = request.new_state
    updated_task = task_repo.update(task)
    db.commit()
    db.refresh(updated_task)
    return updated_task
