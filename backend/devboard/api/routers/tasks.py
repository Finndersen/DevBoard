"""Task API endpoints."""

import datetime
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from devboard.agents.agent_config_service import AgentConfigService
from devboard.api.dependencies.entities import get_verified_task
from devboard.api.dependencies.repositories import (
    get_codebase_repository,
    get_conversation_repository,
    get_document_repository,
    get_task_repository,
)
from devboard.api.dependencies.services import (
    get_agent_config_service,
    get_resource_service,
    get_task_git_service,
    get_task_service,
)
from devboard.api.schemas import (
    DeleteResponse,
    DocumentResponse,
    FileDiff,
    MergeBranchRequest,
    MergeBranchResponse,
    PromptActionRequest,
    ResourceResponse,
    TaskDiffResponse,
    TaskGitStatusResponse,
    TaskResourceCreate,
    TaskResponse,
    TaskUpdate,
)
from devboard.api.streaming import stream_conversation_events
from devboard.db.models import ParentEntityType
from devboard.db.models.task import Task
from devboard.db.repositories import (
    CodebaseRepository,
    ConversationRepository,
    DocumentRepository,
    TaskRepository,
)
from devboard.integrations.git import GitRepoIntegration
from devboard.services.resource_service import (
    ResourceService,
    UnsupportedResourceUriError,
)
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_service import TaskService, TaskTransitionError
from devboard.workflow_actions.registry import workflow_action_registry

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

    return TaskResponse(
        id=task.id,
        title=task.title,
        project_id=task.project_id,
        codebase_id=task.codebase_id,
        status=task.status,
        remote_task_id=task.remote_task_id,
        conversation_id=conversation.id,
        created_at=task.created_at,
        specification=DocumentResponse.model_validate(task.specification),
        implementation_plan=(
            DocumentResponse.model_validate(task.implementation_plan) if task.implementation_plan else None
        ),
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

    # Get active conversation (will raise NoActiveConversationError if not found)
    conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task_id)

    return TaskResponse(
        id=updated_task.id,
        title=updated_task.title,
        project_id=updated_task.project_id,
        codebase_id=updated_task.codebase_id,
        status=updated_task.status,
        remote_task_id=updated_task.remote_task_id,
        conversation_id=conversation.id,
        created_at=updated_task.created_at,
        specification=DocumentResponse.model_validate(updated_task.specification),
        implementation_plan=(
            DocumentResponse.model_validate(updated_task.implementation_plan)
            if updated_task.implementation_plan
            else None
        ),
    )


@router.delete("/{task_id}", response_model=DeleteResponse)
async def delete_task(
    task_id: int,
    task: Task = Depends(get_verified_task),
    task_service: TaskService = Depends(get_task_service),
):
    """Delete a task and all related data (conversations, messages, documents, associations)."""
    # Use the service layer for transactional deletion
    task_service.delete_task(task)

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


@router.get("/{task_id}/diff", response_model=TaskDiffResponse)
async def get_task_diff(
    task_id: int,
    task: Task = Depends(get_verified_task),
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
) -> TaskDiffResponse:
    """Get git diff of uncommitted changes in task's associated codebase.

    Args:
        task_id: ID of the task
        task: Verified task instance
        codebase_repo: Codebase repository

    Returns:
        TaskDiffResponse with per-file diffs and statistics

    Raises:
        HTTPException: 404 if codebase not found, 500 if git operation fails
    """
    # Get codebase
    codebase = codebase_repo.get_by_id(task.codebase_id)
    if not codebase:
        raise HTTPException(
            status_code=404,
            detail=f"Codebase with id {task.codebase_id} not found.",
        )

    # Initialize git integration
    try:
        git_integration = GitRepoIntegration(codebase.local_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize git integration: {str(e)}",
        ) from e

    # Get git diff (all uncommitted changes)
    try:
        raw_diff = await git_integration.get_git_diff(commit1="HEAD")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get git diff: {str(e)}",
        ) from e

    # Parse diff into per-file structures
    files = _parse_git_diff(raw_diff)

    # Calculate totals
    total_additions = sum(f.additions for f in files)
    total_deletions = sum(f.deletions for f in files)

    return TaskDiffResponse(
        files=files,
        total_additions=total_additions,
        total_deletions=total_deletions,
        generated_at=datetime.datetime.now(datetime.UTC),
    )


def _parse_git_diff(raw_diff: str) -> list[FileDiff]:
    """Parse raw git diff output into structured per-file diffs.

    Args:
        raw_diff: Raw git diff output

    Returns:
        List of FileDiff objects, one per changed file
    """
    if not raw_diff.strip():
        return []

    files: list[FileDiff] = []

    # Split by file headers (diff --git lines)
    file_blocks = re.split(r"(?=^diff --git)", raw_diff, flags=re.MULTILINE)

    for block in file_blocks:
        block = block.strip()
        if not block:
            continue

        # Extract file path from +++ b/path line
        file_path_match = re.search(r"^\+\+\+ b/(.+)$", block, re.MULTILINE)
        if not file_path_match:
            # Try --- a/path for deletions
            file_path_match = re.search(r"^--- a/(.+)$", block, re.MULTILINE)

        if not file_path_match:
            continue

        file_path = file_path_match.group(1)

        # Count additions and deletions (lines starting with + or -, but not +++ or ---)
        additions = len(re.findall(r"^\+(?!\+\+)", block, re.MULTILINE))
        deletions = len(re.findall(r"^-(?!--)", block, re.MULTILINE))

        files.append(
            FileDiff(
                file_path=file_path,
                diff_content=block,
                additions=additions,
                deletions=deletions,
            )
        )

    return files


@router.post("/{task_id}/workflow-action")
async def execute_workflow_action(
    task_id: int,
    request: PromptActionRequest,
    task: Task = Depends(get_verified_task),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    task_service: TaskService = Depends(get_task_service),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
) -> StreamingResponse:
    """Stream a task workflow action.

    Workflow actions are reusable, named operations that can send prompts
    to agent conversations or perform structured actions (like task state transitions).
    This endpoint looks up the action by key and executes it, streaming the results.

    Returns events as newline-delimited JSON (NDJSON) for real-time updates.
    Each line is a JSON-serialized ConversationEvent (TextMessage, ToolCall, ToolResult, or SystemEvent).

    Args:
        task_id: ID of the task
        request: Request with action_key to execute
        task: Task instance
        conversation_repo: Repository for conversation operations
        document_repo: Document repository
        task_service: Service for task operations
        agent_config_service: Service for agent configuration

    Raises:
        HTTPException: 404 if action_key not found
        HTTPException: 400 if conversation not active
    """
    # Look up action class in registry
    action_class = workflow_action_registry.get(request.action_key)
    if not action_class:
        raise HTTPException(status_code=404, detail=f"Workflow action '{request.action_key}' not found")

    # Instantiate the task workflow action
    # The action will create the agent service internally when needed
    action = action_class(
        task=task,
        task_service=task_service,
        conversation_repo=conversation_repo,
        agent_config_service=agent_config_service,
        document_repository=document_repo,
    )

    # Define exception handler to convert task transition errors to HTTP exceptions
    def handle_exception(exc: Exception) -> None:
        """Convert task transition errors to appropriate HTTP exceptions."""
        if isinstance(exc, TaskTransitionError):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise exc

    # Stream events from the action
    return stream_conversation_events(action.run(), exception_handler=handle_exception)


# Git endpoints


@router.get("/{task_id}/git-status", response_model=TaskGitStatusResponse)
async def get_task_git_status(
    task_id: int,
    task: Task = Depends(get_verified_task),
    task_git_service: TaskGitService = Depends(get_task_git_service),
) -> TaskGitStatusResponse:
    """Get git status for a task's branch.

    Returns information about the task's git branch including:
    - Branch existence
    - Commits ahead/behind base branch
    - Merge conflicts
    - Merge readiness

    Raises:
        HTTPException: 404 if task not found, 400 if operation fails
    """
    try:
        status = await task_git_service.get_task_git_status(task)
        return TaskGitStatusResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{task_id}/merge-branch", response_model=MergeBranchResponse)
async def merge_task_branch(
    task_id: int,
    request: MergeBranchRequest,
    task: Task = Depends(get_verified_task),
    task_git_service: TaskGitService = Depends(get_task_git_service),
) -> MergeBranchResponse:
    """Merge a task's branch into its base branch.

    Optionally deletes the task branch after successful merge.

    Args:
        task_id: ID of the task
        request: Merge configuration (target branch, delete after merge)

    Returns:
        Merge result with commit hash

    Raises:
        HTTPException: 404 if task not found, 400 if merge fails
    """
    if not task.branch_name:
        raise HTTPException(status_code=400, detail="Task has no branch configured")

    try:
        merge_commit = await task_git_service.merge_task_branch(
            task,
            target_branch=request.target_branch,
            delete_branch=request.delete_branch,
        )
        return MergeBranchResponse(
            success=True,
            merge_commit=merge_commit,
            message=f"Successfully merged {task.branch_name} into {request.target_branch or task.base_branch}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{task_id}/branch")
async def delete_task_branch(
    task_id: int,
    force: bool = False,
    task: Task = Depends(get_verified_task),
    task_git_service: TaskGitService = Depends(get_task_git_service),
) -> DeleteResponse:
    """Delete a task's git branch.

    Args:
        task_id: ID of the task
        force: Force deletion even if not fully merged

    Returns:
        Deletion confirmation

    Raises:
        HTTPException: 404 if task not found, 400 if deletion fails
    """
    if not task.branch_name:
        raise HTTPException(status_code=400, detail="Task has no branch configured")

    try:
        await task_git_service.delete_task_branch(task, force=force)
        return DeleteResponse(
            success=True,
            message=f"Successfully deleted branch {task.branch_name}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
