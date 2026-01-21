"""Task API endpoints."""

import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from devboard.agents.agent_config_service import AgentConfigService
from devboard.api.dependencies.entities import get_verified_task
from devboard.api.dependencies.repositories import (
    get_conversation_repository,
    get_document_repository,
    get_task_repository,
    get_worktree_slot_repository,
)
from devboard.api.dependencies.services import (
    get_agent_config_service,
    get_integration_service,
    get_resource_service,
    get_task_git_service,
    get_task_service,
    get_workspace_allocation_service,
)
from devboard.api.schemas import (
    CheckoutToMainResponse,
    CommitMetadata,
    DeleteResponse,
    FileDiff,
    GitHubPRStatusResponse,
    MergeBranchRequest,
    MergeBranchResponse,
    PromptActionRequest,
    ResourceResponse,
    TaskBranchInfo,
    TaskDiffResponse,
    TaskGitStatusResponse,
    TaskResourceCreate,
    TaskResponse,
    TaskUpdate,
    WorkflowActionInfo,
)
from devboard.api.streaming import stream_conversation_events
from devboard.db.models import ParentEntityType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories import (
    ConversationRepository,
    DocumentRepository,
    TaskRepository,
    WorktreeSlotRepository,
)
from devboard.integrations.github import GitHubIntegration
from devboard.services.integration_service import IntegrationService
from devboard.services.resource_service import (
    ResourceService,
    UnsupportedResourceUriError,
)
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_service import TaskService, TaskTransitionError
from devboard.services.workspace_allocation_service import WorkspaceAllocationService
from devboard.workflow_actions.registry import workflow_action_registry

router = APIRouter()


def _get_available_workflow_actions(task: Task) -> list[WorkflowActionInfo]:
    """Get list of available workflow actions for a task."""
    available_actions = []

    for action_class in workflow_action_registry.list_values():
        if action_class.is_available(task):
            available_actions.append(
                WorkflowActionInfo(
                    key=action_class.KEY, label=action_class.KEY.replace("task.", "").replace("_", " ").title()
                )
            )

    return available_actions


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    task: Task = Depends(get_verified_task),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> TaskResponse:
    """Get a specific task with active conversation_id."""
    # Get active conversation (should always exist since created at task creation)
    conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task_id)

    # Get available workflow actions
    available_actions = _get_available_workflow_actions(task)

    return TaskResponse(
        id=task.id,
        title=task.title,
        project_id=task.project_id,
        codebase_id=task.codebase_id,
        status=task.status,
        remote_task_id=task.remote_task_id,
        conversation_id=conversation.id,
        created_at=task.created_at,
        specification_document_id=task.specification.id,
        implementation_plan_document_id=task.implementation_plan.id if task.implementation_plan else None,
        change_summary_document_id=task.change_summary.id if task.change_summary else None,
        available_workflow_actions=available_actions,
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

    # Get available workflow actions
    available_actions = _get_available_workflow_actions(updated_task)

    return TaskResponse(
        id=updated_task.id,
        title=updated_task.title,
        project_id=updated_task.project_id,
        codebase_id=updated_task.codebase_id,
        status=updated_task.status,
        remote_task_id=updated_task.remote_task_id,
        conversation_id=conversation.id,
        created_at=updated_task.created_at,
        specification_document_id=updated_task.specification.id,
        implementation_plan_document_id=(
            updated_task.implementation_plan.id if updated_task.implementation_plan else None
        ),
        change_summary_document_id=(updated_task.change_summary.id if updated_task.change_summary else None),
        available_workflow_actions=available_actions,
    )


@router.delete("/{task_id}", response_model=DeleteResponse)
async def delete_task(
    task_id: int,
    delete_branch: bool = False,
    task: Task = Depends(get_verified_task),
    task_service: TaskService = Depends(get_task_service),
):
    """Delete a task and all related data (conversations, messages, documents, associations).

    Args:
        task_id: ID of the task to delete
        delete_branch: If True, also delete the task's git branch (if it exists)
        task: Verified task instance
        task_service: Task service instance

    Returns:
        Deletion confirmation
    """
    # Use the service layer for transactional deletion
    await task_service.delete_task(task, delete_branch=delete_branch)

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
        return created_resource
    except UnsupportedResourceUriError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
    view: str,
    task: Task = Depends(get_verified_task),
    task_git_service: TaskGitService = Depends(get_task_git_service),
) -> TaskDiffResponse:
    """Get git diff for a task.

    Requires 'view' query parameter to specify what to show:
    - view=all: Combined diff (all changes including uncommitted if worktree exists)
    - view=uncommitted: Only uncommitted changes (empty if no worktree)
    - view=<commit_hash>: Diff for a specific commit

    The service automatically determines the appropriate repository path:
    - For uncommitted changes: uses worktree slot if available
    - For all changes: uses worktree if available, otherwise main codebase
    - For commit diffs: always uses main codebase

    Args:
        task_id: ID of the task
        view: Required view filter (all|uncommitted|<commit_hash>)
        task: Verified task instance
        task_git_service: Task git service

    Returns:
        TaskDiffResponse with file diffs

    Raises:
        HTTPException: 400 if view not provided, 500 if git operation fails
    """
    # Get diff using service - returns StructuredDiff
    diff = await task_git_service.get_task_diff_by_view(task, view)

    # Convert StructuredDiff to TaskDiffResponse
    return TaskDiffResponse(
        files=[
            FileDiff(
                file_path=file.file_path,
                diff_content=file.diff_content,
                additions=file.additions,
                deletions=file.deletions,
            )
            for file in diff.files
        ],
        additions=diff.additions,
        deletions=diff.deletions,
        generated_at=datetime.datetime.now(datetime.UTC),
    )


@router.post("/{task_id}/workflow-action")
async def execute_workflow_action(
    task_id: int,
    request: PromptActionRequest,
    task: Task = Depends(get_verified_task),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    task_service: TaskService = Depends(get_task_service),
    task_git_service: TaskGitService = Depends(get_task_git_service),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
    workspace_allocation_service: WorkspaceAllocationService = Depends(get_workspace_allocation_service),
    integration_service: IntegrationService = Depends(get_integration_service),
) -> StreamingResponse:
    """Stream a task workflow action.

    Workflow actions are reusable, named operations that can send prompts
    to agent conversations or perform structured actions (like task state transitions).
    This endpoint looks up the action by key and executes it, streaming the results.

    Returns events as newline-delimited JSON (NDJSON) for real-time updates.
    Each line is a JSON-serialized ConversationEvent (TextMessage, ToolCall, ToolResult, or SystemEvent).

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
        task_git_service=task_git_service,
        conversation_repo=conversation_repo,
        agent_config_service=agent_config_service,
        document_repository=document_repo,
        workspace_allocation_service=workspace_allocation_service,
        integration_service=integration_service,
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


@router.get("/{task_id}/branch-info", response_model=TaskBranchInfo)
async def get_task_branch_info(
    task_id: int,
    task: Task = Depends(get_verified_task),
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
    task_git_service: TaskGitService = Depends(get_task_git_service),
    workspace_allocation_service: WorkspaceAllocationService = Depends(get_workspace_allocation_service),
) -> TaskBranchInfo:
    """Get branch information for a task.

    Returns lightweight commit metadata and uncommitted changes flag.
    Used to populate UI dropdowns for selecting what diff to view.

    Returns:
        TaskBranchInfo with commits list and has_uncommitted_changes flag

    Raises:
        HTTPException: 404 if task not found, 500 if git operation fails
    """
    # Get the most recently used worktree slot for this task
    last_used_slot = worktree_slot_repo.get_last_used_slot_for_task(task.id)

    # Get commit metadata from main codebase (not worktree)
    commit_entries = await task_git_service.get_task_commit_metadata(task)

    # Check for uncommitted changes only if there's a worktree slot
    has_uncommitted = False
    if last_used_slot:
        has_uncommitted = await workspace_allocation_service.slot_has_uncommitted_changes(last_used_slot)

    # Convert GitLogEntry to CommitMetadata schema
    commits = [
        CommitMetadata(
            commit_hash=entry.hash,
            author=entry.author,
            date=entry.date,
            message=entry.message,
        )
        for entry in commit_entries
    ]

    return TaskBranchInfo(
        commits=commits,
        has_uncommitted_changes=has_uncommitted,
    )


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

    TODO: Merge with above get_task_branch_info() endpoint

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


@router.post("/{task_id}/checkout-to-main", response_model=CheckoutToMainResponse)
async def checkout_task_to_main(
    task_id: int,
    task: Task = Depends(get_verified_task),
    workspace_allocation_service: WorkspaceAllocationService = Depends(get_workspace_allocation_service),
) -> CheckoutToMainResponse:
    """Checkout a task's branch to the main repository.

    This operation:
    1. Detaches HEAD in the worktree currently holding the branch (if any)
    2. Checks out the task's branch in the main repository
    3. Assigns the task to the main repo WorktreeSlot

    Args:
        task_id: ID of the task

    Returns:
        Checkout result confirmation

    Raises:
        HTTPException: 400 if task has no branch, main repo has uncommitted changes,
                       or git operation fails
    """
    if not task.branch_name:
        raise HTTPException(status_code=400, detail="Task has no branch configured")

    try:
        await workspace_allocation_service.checkout_task_to_main_repo(task)
        return CheckoutToMainResponse(
            success=True,
            message=f"Successfully checked out {task.branch_name} to main repository",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{task_id}/pr-status", response_model=GitHubPRStatusResponse)
async def get_task_pr_status(
    task_id: int,
    task: Task = Depends(get_verified_task),
    task_service: TaskService = Depends(get_task_service),
    integration_service: IntegrationService = Depends(get_integration_service),
) -> GitHubPRStatusResponse:
    """Get GitHub PR status for a task in PR_OPEN state.

    Returns PR information including merge status, mergeable state, and checks status.
    Used by frontend to enable/disable merge actions and display PR status.

    Args:
        task_id: ID of the task

    Returns:
        GitHubPRStatusResponse with PR status information

    Raises:
        HTTPException: 404 if task not in PR_OPEN state or has no PR reference
        HTTPException: 500 if GitHub API fails
    """
    # Validate task is in PR_OPEN state
    if task.status != TaskStatus.PR_OPEN:
        raise HTTPException(status_code=404, detail=f"Task is not in PR_OPEN state (current: {task.status.value})")

    # Check task has PR info
    if not task.github_pr_number:
        raise HTTPException(status_code=404, detail="Task has no PR configured")

    # Check codebase has repository URL
    if not task.codebase.repository_url:
        raise HTTPException(status_code=404, detail="Task codebase has no repository URL configured")

    # Get GitHub integration and repository wrapper
    try:
        github = integration_service.get_integration_instance(GitHubIntegration)
        github_repo = await github.get_repository_from_url(task.codebase.repository_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub integration not configured: {e}") from e

    try:
        github_pr = await github_repo.get_pull_request(task.github_pr_number)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch PR status: {e}") from e

    pr = github_pr.pr
    # Determine aggregate checks status from mergeable_state
    checks_status = None
    if pr.mergeable_state:
        if pr.mergeable_state == "clean":
            checks_status = "success"
        elif pr.mergeable_state in ("blocked", "behind", "dirty"):
            checks_status = "pending"
        elif pr.mergeable_state == "unstable":
            checks_status = "failure"

    return GitHubPRStatusResponse(
        merged=pr.merged,
        mergeable=pr.mergeable,
        mergeable_state=pr.mergeable_state or "unknown",
        state=pr.state,
        review_comments_count=pr.review_comments,
        checks_status=checks_status,
        pr_url=pr.html_url,
    )
