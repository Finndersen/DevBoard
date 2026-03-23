"""Task API endpoints."""

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution.registry import get_execution_manager
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
    get_task_implementation_plan_service,
    get_task_service,
    get_workspace_service,
)
from devboard.api.schemas import (
    CheckoutToMainResponse,
    CommitMetadata,
    DeleteResponse,
    FileDiff,
    GitHubPRStatusResponse,
    ImplementationPlanResponse,
    ImplementationStepResponse,
    ImplementationStepUpdate,
    MergeBranchRequest,
    MergeBranchResponse,
    PRFeedbackCommentResponse,
    PRFeedbackCommentThreadResponse,
    PRFeedbackResponse,
    PRFeedbackReviewResponse,
    PromptActionRequest,
    TaskBranchInfo,
    TaskDiffResponse,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
    WorkflowActionInfo,
)
from devboard.db.models import ParentEntityType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories import (
    ConversationRepository,
    DocumentRepository,
    TaskRepository,
    WorktreeSlotRepository,
)
from devboard.integrations.base import IntegrationError
from devboard.integrations.github import CommentThread, GitHubIntegration, ReviewComment
from devboard.services.integration_service import IntegrationService
from devboard.services.task_git import TaskGitStatus
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_implementation_plan import TaskImplementationPlanService
from devboard.services.task_service import TaskService
from devboard.services.workspace import WorkspaceService
from devboard.services.workspace.pool_manager import WorktreePoolManager
from devboard.workflow_actions.registry import workflow_action_registry

router = APIRouter()


def _get_available_workflow_actions(task: Task) -> list[WorkflowActionInfo]:
    """Get list of available workflow actions for a task."""
    available_actions: list[WorkflowActionInfo] = []

    for action_class in workflow_action_registry.list_values():
        if action_class.is_available(task):
            available_actions.append(WorkflowActionInfo(key=action_class.KEY))

    return available_actions


@router.get("/", response_model=list[TaskListResponse])
async def list_all_tasks(
    project_id: int | None = Query(None),
    status: list[TaskStatus] | None = Query(None),
    task_repo: TaskRepository = Depends(get_task_repository),
) -> list[TaskListResponse]:
    """Fetch all tasks across projects with optional project and status filtering."""
    tasks = task_repo.get_list(project_id=project_id, statuses=status, with_project=True)

    return [
        TaskListResponse(
            id=task.id,
            title=task.title,
            project_id=task.project_id,
            project_name=task.project.name,
            codebase_id=task.codebase_id,
            status=task.status,
            created_at=task.created_at,
        )
        for task in tasks
    ]


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
        conversation_id=conversation.id,
        created_at=task.created_at,
        specification_document_id=task.specification.id,
        implementation_plan_document_id=task.implementation_plan.id if task.implementation_plan else None,
        change_summary_document_id=task.change_summary.id if task.change_summary else None,
        implementation_plan_id=(
            task.implementation_plan_structured.id if task.implementation_plan_structured else None
        ),
        custom_fields=task.custom_fields,
        available_workflow_actions=available_actions,
        github_pr_number=task.github_pr_number,
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
        assert task.implementation_plan is not None
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
        conversation_id=conversation.id,
        created_at=updated_task.created_at,
        specification_document_id=updated_task.specification.id,
        implementation_plan_document_id=(
            updated_task.implementation_plan.id if updated_task.implementation_plan else None
        ),
        change_summary_document_id=(updated_task.change_summary.id if updated_task.change_summary else None),
        implementation_plan_id=(
            updated_task.implementation_plan_structured.id if updated_task.implementation_plan_structured else None
        ),
        custom_fields=updated_task.custom_fields,
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


@router.get("/{task_id}/diff", response_model=TaskDiffResponse)
async def get_task_diff(
    task_id: int,
    view: str,
    task: Task = Depends(get_verified_task),
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

    Returns:
        TaskDiffResponse with file diffs

    Raises:
        HTTPException: 400 if view not provided, 500 if git operation fails
    """
    # Get diff using service - returns StructuredDiff
    diff = await TaskGitService.get_task_diff_by_view(task, view)

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
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
    integration_service: IntegrationService = Depends(get_integration_service),
) -> dict[str, Any]:
    """Execute a task workflow action.

    Runs the action's procedural steps (state transitions, DB changes) synchronously.
    If the action returns a prompt, starts a background agent execution on the task's
    active conversation and returns its ID. Otherwise returns a completion status.

    Connect to GET /api/conversations/{conversation_id}/ws to receive agent events.

    Returns:
        {"conversation_id": <id>} if agent execution started
        {"status": "completed"} if no agent interaction needed

    Raises:
        HTTPException 400: if action validation fails (e.g. GitHub connection)
        HTTPException 404: if action_key not found or no active conversation
        HTTPException 409: if an execution is already active for this conversation
    """
    action_class = workflow_action_registry.get(request.action_key)
    if not action_class:
        raise HTTPException(status_code=404, detail=f"Workflow action '{request.action_key}' not found")

    action = action_class(
        task=task,
        task_service=task_service,
        conversation_repo=conversation_repo,
        agent_config_service=agent_config_service,
        document_repository=document_repo,
        integration_service=integration_service,
    )

    try:
        prompt = await action.run()
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    if prompt is None:
        return {"status": "completed"}

    # Get active conversation (may have changed after action.run(), e.g. BeginImplementation)
    conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task_id)
    if not conversation:
        raise HTTPException(status_code=404, detail=f"No active conversation found for task {task_id}")

    cid = conversation.id
    try:
        get_execution_manager().start_agent_execution(cid, prompt)
    except ConversationBusyError as err:
        raise HTTPException(status_code=409, detail="An execution is already active for this conversation") from err

    return {"conversation_id": cid, "prompt": prompt}


# Git endpoints


@router.get("/{task_id}/branch-info", response_model=TaskBranchInfo)
async def get_task_branch_info(
    task_id: int,
    task: Task = Depends(get_verified_task),
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
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
    commit_entries = await TaskGitService.get_task_commit_metadata(task)

    # Check for uncommitted changes only if there's a worktree slot
    has_uncommitted = False
    if last_used_slot:
        pool_manager = WorktreePoolManager(worktree_slot_repo=worktree_slot_repo)
        has_uncommitted = await pool_manager.slot_has_uncommitted_changes(last_used_slot)

    # Convert GitLogEntry to CommitMetadata schema
    commits = [
        CommitMetadata(
            commit_hash=entry.hash,
            author=entry.author,
            date=entry.date,
            message=entry.subject,
        )
        for entry in commit_entries
    ]

    return TaskBranchInfo(
        commits=commits,
        has_uncommitted_changes=has_uncommitted,
    )


@router.get("/{task_id}/git-status", response_model=TaskGitStatus)
async def get_task_git_status(
    task_id: int,
    task: Task = Depends(get_verified_task),
) -> TaskGitStatus:
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
        status = await TaskGitService.get_task_git_status(task)
        return status
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{task_id}/merge-branch", response_model=MergeBranchResponse)
async def merge_task_branch(
    task_id: int,
    request: MergeBranchRequest,
    task: Task = Depends(get_verified_task),
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
    try:
        merge_commit = await TaskGitService.merge_task_branch(
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
    try:
        await TaskGitService.delete_task_branch(task, force=force)
        return DeleteResponse(
            success=True,
            message=f"Successfully deleted branch {task.branch_name}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{task_id}/abort-rebase", response_model=DeleteResponse)
async def abort_task_rebase(
    task_id: int,
    task: Task = Depends(get_verified_task),
) -> DeleteResponse:
    """Abort an in-progress rebase for a task.

    Args:
        task_id: ID of the task

    Returns:
        Success confirmation

    Raises:
        HTTPException: 400 if task has no branch, no rebase in progress, or abort fails
    """
    try:
        await TaskGitService.abort_rebase(task)
        return DeleteResponse(
            success=True,
            message="Rebase aborted successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{task_id}/create-branch", response_model=DeleteResponse)
async def create_task_branch(
    task_id: int,
    task: Task = Depends(get_verified_task),
) -> DeleteResponse:
    """Create (or recreate) the git branch for a task.

    Uses TaskGitService.create_task_branch which is idempotent — skips if branch
    already exists, creates from task.base_branch if not.

    Returns:
        Success confirmation

    Raises:
        HTTPException: 400 if branch creation fails
    """
    try:
        await TaskGitService.create_task_branch(task)
        return DeleteResponse(
            success=True,
            message=f"Branch {task.branch_name} created successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{task_id}/checkout-to-main", response_model=CheckoutToMainResponse)
async def checkout_task_to_main(
    task_id: int,
    task: Task = Depends(get_verified_task),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
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
    try:
        await workspace_service.checkout_task_to_main_repo(task)
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
    """Get GitHub PR status for a task that has a PR.

    Returns PR information including merge status, mergeable state, and checks status.
    Supported for tasks in PR_OPEN or COMPLETE state (PR number persists after completion).
    """
    # Validate task has (or had) a PR
    if task.status not in (TaskStatus.PR_OPEN, TaskStatus.COMPLETE):
        raise HTTPException(status_code=404, detail=f"Task has no PR (current status: {task.status.value})")

    # Check task has PR info
    if not task.github_pr_number:
        raise HTTPException(status_code=404, detail="Task has no PR configured")

    # Check codebase has repository URL
    if not task.codebase.repository_url:
        raise HTTPException(status_code=404, detail="Task codebase has no repository URL configured")

    try:
        github = integration_service.get_integration_instance(GitHubIntegration)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub integration not configured: {e}") from e

    try:
        owner, repo = GitHubIntegration.parse_repo_url(task.codebase.repository_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid repository URL: {e}") from e

    try:
        pr = await github.get_pull_request_status(owner, repo, task.github_pr_number)
    except IntegrationError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg) from e
        raise HTTPException(status_code=500, detail=f"Failed to fetch PR status: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch PR status: {e}") from e

    return GitHubPRStatusResponse(
        pr_number=pr.number,
        pr_url=pr.html_url,
        state=pr.state,
        merged=pr.state == "MERGED",
        mergeable_state=pr.mergeable_state,
        review_decision=pr.review_decision,
        ci_status=pr.ci_status,
        comment_count=pr.comment_count,
    )


def _map_comment(comment: ReviewComment) -> PRFeedbackCommentResponse:
    return PRFeedbackCommentResponse(
        id=comment.id,
        author=comment.author,
        body=comment.body,
        path=comment.path,
        line=comment.line,
        diff_hunk=comment.diff_hunk,
        created_at=comment.created_at,
        in_reply_to_id=comment.in_reply_to_id,
    )


def _map_thread(thread: CommentThread) -> PRFeedbackCommentThreadResponse:
    return PRFeedbackCommentThreadResponse(
        original=_map_comment(thread.original),
        replies=[_map_comment(r) for r in thread.replies],
    )


@router.get("/{task_id}/pr-feedback", response_model=PRFeedbackResponse)
async def get_task_pr_feedback(
    task_id: int,
    task: Task = Depends(get_verified_task),
    integration_service: IntegrationService = Depends(get_integration_service),
) -> PRFeedbackResponse:
    """Get GitHub PR feedback (reviews and comments) for a task in PR_OPEN state.

    Returns structured review feedback including inline comment threads and
    standalone comment threads, suitable for rendering in the diff view.
    """
    if task.status != TaskStatus.PR_OPEN:
        raise HTTPException(status_code=404, detail=f"Task is not in PR_OPEN state (current: {task.status.value})")

    if not task.github_pr_number:
        raise HTTPException(status_code=404, detail="Task has no PR configured")

    if not task.codebase.repository_url:
        raise HTTPException(status_code=404, detail="Task codebase has no repository URL configured")

    try:
        github = integration_service.get_integration_instance(GitHubIntegration)
        github_repo = await github.get_repository_from_url(task.codebase.repository_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub integration not configured: {e}") from e

    try:
        github_pr = await github_repo.get_pull_request(task.github_pr_number)
        feedback = await github_pr.get_feedback()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch PR feedback: {e}") from e

    return PRFeedbackResponse(
        reviews=[
            PRFeedbackReviewResponse(
                id=review.id,
                author=review.author,
                state=review.state,
                body=review.body,
                submitted_at=review.submitted_at,
                comment_threads=[_map_thread(t) for t in review.comment_threads],
            )
            for review in feedback.reviews
        ],
        standalone_threads=[_map_thread(t) for t in feedback.standalone_threads],
    )


# Implementation Plan endpoints


@router.get("/{task_id}/implementation-plan", response_model=ImplementationPlanResponse)
async def get_implementation_plan(
    task_id: int,
    task: Task = Depends(get_verified_task),
    plan_service: TaskImplementationPlanService = Depends(get_task_implementation_plan_service),
) -> ImplementationPlanResponse:
    """Get the structured implementation plan for a task."""
    plan = plan_service.get_plan_by_task_id(task_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No implementation plan found for this task")

    return ImplementationPlanResponse(
        id=plan.id,
        task_id=plan.task_id,
        overview=plan.overview,
        status=plan.status,
        steps=[
            ImplementationStepResponse(
                id=step.id,
                step_number=step.step_number,
                title=step.title,
                type=step.type,
                dependencies=step.dependencies or [],
                status=step.status,
                details=step.details,
                outcome=step.outcome,
                conversation_id=step.conversation_id,
                started_at=step.started_at,
                completed_at=step.completed_at,
            )
            for step in plan.steps
        ],
    )


@router.patch(
    "/{task_id}/implementation-plan/steps/{step_number}",
    response_model=ImplementationStepResponse,
)
async def update_implementation_step(
    task_id: int,
    step_number: int,
    step_update: ImplementationStepUpdate,
    task: Task = Depends(get_verified_task),
    plan_service: TaskImplementationPlanService = Depends(get_task_implementation_plan_service),
) -> ImplementationStepResponse:
    """Update a specific implementation step by step number."""
    plan = plan_service.get_plan_by_task_id(task_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No implementation plan found for this task")

    update_fields = step_update.model_dump(exclude_unset=True)
    try:
        step = plan_service.update_step(plan, step_number, **update_fields)
    except ValueError as e:
        # Return 404 for missing step, 400 for other validation errors
        status_code = 404 if "not found" in str(e) else 400
        raise HTTPException(status_code=status_code, detail=str(e)) from e
    plan_service.commit()

    return ImplementationStepResponse(
        id=step.id,
        step_number=step.step_number,
        title=step.title,
        type=step.type,
        dependencies=step.dependencies or [],
        status=step.status,
        details=step.details,
        outcome=step.outcome,
        conversation_id=step.conversation_id,
        started_at=step.started_at,
        completed_at=step.completed_at,
    )
