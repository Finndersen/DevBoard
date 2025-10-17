"""Task API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.entities import get_verified_task
from devboard.api.dependencies.repositories import (
    get_conversation_repository,
    get_document_repository,
    get_task_repository,
)
from devboard.api.dependencies.services import get_resource_service, get_task_service
from devboard.api.schemas import (
    DeleteResponse,
    ResourceResponse,
    StateTransitionRequest,
    TaskResourceCreate,
    TaskResponse,
    TaskUpdate,
)
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories import (
    ConversationRepository,
    DocumentRepository,
    TaskRepository,
)
from devboard.services.resource_service import (
    ResourceService,
    UnsupportedResourceUriError,
)
from devboard.services.task_service import TaskService

router = APIRouter()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    task: Task = Depends(get_verified_task),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> TaskResponse:
    """Get a specific task with active conversation_id."""
    # Get active conversation (should always exist since created at task creation)
    conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task_id)

    if not conversation:
        # This should never happen for tasks created after this change
        # For legacy tasks without conversations, this is a data integrity issue
        raise HTTPException(
            status_code=500,
            detail="Task has no active conversation. Data integrity issue.",
        )

    return TaskResponse(
        id=task.id,
        title=task.title,
        project_id=task.project_id,
        codebase_id=task.codebase_id,
        status=task.status,
        remote_task_id=task.remote_task_id,
        conversation_id=conversation.id,
        created_at=task.created_at,
        specification=task.specification,
        implementation_plan=task.implementation_plan,
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    task: Task = Depends(get_verified_task),
    task_repo: TaskRepository = Depends(get_task_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
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
        # Update the implementation plan document content
        document_repo.update_content(task.implementation_plan, implementation_plan)

    # Update other task fields
    for field, value in update_data.items():
        setattr(task, field, value)

    updated_task = task_repo.update(task)
    task_repo.db.commit()
    task_repo.db.refresh(updated_task)

    # Get active conversation
    conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task_id)
    if not conversation:
        raise HTTPException(status_code=500, detail="Task has no active conversation. Data integrity issue.")

    return TaskResponse(
        id=updated_task.id,
        title=updated_task.title,
        project_id=updated_task.project_id,
        codebase_id=updated_task.codebase_id,
        status=updated_task.status,
        remote_task_id=updated_task.remote_task_id,
        conversation_id=conversation.id,
        created_at=updated_task.created_at,
        specification=updated_task.specification,
        implementation_plan=updated_task.implementation_plan,
    )


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


@router.post("/{task_id}/state-transition", response_model=TaskResponse)
async def transition_task_state(
    task_id: int,
    request: StateTransitionRequest,
    task: Task = Depends(get_verified_task),
    task_repo: TaskRepository = Depends(get_task_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    task_service: TaskService = Depends(get_task_service),
):
    """Transition task to a new lifecycle state.

    This endpoint handles the state transition process:
    1. Validates the transition is allowed (checks prerequisites)
    2. Creates required documents (e.g., implementation_plan for PLANNING)
    3. Updates the task status
    4. Archives the current conversation
    5. Creates a new conversation for the new phase with appropriate agent role

    The frontend should follow up with a call to the prompt-action endpoint
    to initialize the new phase's agent with an appropriate prompt.

    Args:
        task_id: ID of the task to transition
        request: Request with new_state to transition to
        task: Verified task instance
        task_repo: Task repository
        document_repo: Document repository
        conversation_repo: Conversation repository
        task_service: Task service for transition logic

    Returns:
        Updated TaskResponse with new conversation_id

    Raises:
        HTTPException: 400 if state invalid or transition not allowed
    """
    # Validate state
    if request.new_state not in TaskStatus:
        raise HTTPException(status_code=400, detail=f"Invalid state: {request.new_state}")

    # Validate transition is allowed (checks prerequisites like spec content, plan content, etc.)
    can_transition, error_message = task_service.can_transition_to_phase(task, request.new_state)
    if not can_transition:
        raise HTTPException(status_code=400, detail=error_message)

    # Create implementation_plan document if transitioning to PLANNING and it doesn't exist
    if request.new_state == TaskStatus.PLANNING and not task.implementation_plan:
        implementation_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        task.implementation_plan_id = implementation_plan_doc.id
        task.implementation_plan = implementation_plan_doc

    # Update task status
    task.status = request.new_state
    updated_task = task_repo.update(task)

    # Create new conversation for the new phase (archives old conversation automatically)
    new_conversation = task_service.create_conversation_for_task_phase(updated_task, request.new_state)

    # Commit all changes
    task_repo.db.commit()
    task_repo.db.refresh(updated_task)
    task_repo.db.refresh(new_conversation)

    return TaskResponse(
        id=updated_task.id,
        title=updated_task.title,
        project_id=updated_task.project_id,
        codebase_id=updated_task.codebase_id,
        status=updated_task.status,
        remote_task_id=updated_task.remote_task_id,
        conversation_id=new_conversation.id,
        created_at=updated_task.created_at,
        specification=updated_task.specification,
        implementation_plan=updated_task.implementation_plan,
    )
