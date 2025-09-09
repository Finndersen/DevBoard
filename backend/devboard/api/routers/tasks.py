"""Task API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from devboard.api.schemas import (
    ApplyEditsRequest,
    DeleteResponse,
    ResourceResponse,
    StateTransitionRequest,
    TaskConversationMessage,
    TaskCreate,
    TaskPlanningRequest,
    TaskResourceCreate,
    TaskResponse,
    TaskUpdate,
)
from devboard.db.database import get_db
from devboard.db.models import Task
from devboard.db.models import TaskConversationMessage as TaskConversationMessageModel
from devboard.db.repositories import (
    ProjectRepository,
    TaskConversationMessageRepository,
    TaskRepository,
)
from devboard.services.document_editor import document_editor_service
from devboard.services.resource_service import ResourceService, UnsupportedResourceUriError
from devboard.services.task_planning_agent import task_planning_agent_service

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

    # Create task
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
            task_id=task_id, resource_uri=resource.resource_uri, description=resource.description
        )
        db.commit()
        db.refresh(created_resource)
        return created_resource
    except UnsupportedResourceUriError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/{task_id}/resources/{resource_id}", response_model=DeleteResponse)
async def delete_task_resource(task_id: int, resource_id: int, db: Session = Depends(get_db)):
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


@router.get("/{task_id}/messages", response_model=list[TaskConversationMessage])
async def get_task_messages(task_id: int, db: Session = Depends(get_db)):
    """Get conversation history for a task."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get task messages
    message_repo = TaskConversationMessageRepository(db)
    messages = message_repo.get_by_task(task_id)
    return messages


@router.post("/{task_id}/messages", response_model=TaskConversationMessage)
async def send_task_message(
    task_id: int, request: TaskPlanningRequest, db: Session = Depends(get_db)
):
    """Send a message to the task planning agent."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        # Store user message
        message_repo = TaskConversationMessageRepository(db)
        user_message = TaskConversationMessageModel(
            task_id=task_id,
            role="user",
            content=request.message
        )
        message_repo.create(user_message)

        # Process message with agent
        agent_response = await task_planning_agent_service.process_message(
            task_id=task_id,
            task_title=task.title,
            task_description=task.description,
            task_implementation_plan=task.implementation_plan,
            task_state=task.status,
            project_id=task.project_id,
            user_message=request.message,
        )

        # Store agent response
        agent_message = TaskConversationMessageModel(
            task_id=task_id,
            role="assistant",
            content=agent_response.message,
            tool_data={
                "task_specification_edits": [edit.model_dump() for edit in agent_response.task_specification_edits] if agent_response.task_specification_edits else None,
                "task_implementation_plan_edits": [edit.model_dump() for edit in agent_response.task_implementation_plan_edits] if agent_response.task_implementation_plan_edits else None,
            }
        )
        saved_agent_message = message_repo.create(agent_message)

        db.commit()
        db.refresh(saved_agent_message)
        return saved_agent_message

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}") from e


@router.post("/{task_id}/apply-edits", response_model=TaskResponse)
async def apply_document_edits(
    task_id: int, request: ApplyEditsRequest, db: Session = Depends(get_db)
):
    """Apply structured document edits from agent response."""
    # Verify task exists
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Verify message exists
    message_repo = TaskConversationMessageRepository(db)
    message = message_repo.get_by_id(request.message_id)
    if not message or message.task_id != task_id:
        raise HTTPException(status_code=404, detail="Message not found")

    try:
        errors = []

        # Apply specification edits
        if request.task_specification_edits:
            current_content = task.description or ""
            edit_result = document_editor_service.apply_edits(current_content, request.task_specification_edits)
            if edit_result.success:
                task.description = edit_result.content
            else:
                errors.append(f"Specification edit failed: {edit_result.error}")

        # Apply implementation plan edits
        if request.task_implementation_plan_edits:
            current_content = task.implementation_plan or ""
            edit_result = document_editor_service.apply_edits(current_content, request.task_implementation_plan_edits)
            if edit_result.success:
                task.implementation_plan = edit_result.content
            else:
                errors.append(f"Implementation plan edit failed: {edit_result.error}")

        if errors:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Edit application failed: {'; '.join(errors)}")

        # Update task
        updated_task = task_repo.update(task)
        db.commit()
        db.refresh(updated_task)
        return updated_task

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error applying edits: {str(e)}") from e


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

    # Validate state transition
    valid_states = ["Pending", "Designing", "Planning", "Implementing", "In Review", "Complete"]
    if request.new_state not in valid_states:
        raise HTTPException(status_code=400, detail=f"Invalid state: {request.new_state}")

    # Update task status
    task.status = request.new_state
    updated_task = task_repo.update(task)
    db.commit()
    db.refresh(updated_task)
    return updated_task
