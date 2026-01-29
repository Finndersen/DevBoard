"""Task Pydantic schemas."""

import datetime
from typing import Any

from pydantic import BaseModel

from devboard.db.models.task import TaskStatus


class TaskBase(BaseModel):
    """Base task schema."""

    title: str
    project_id: int
    codebase_id: int
    status: TaskStatus = TaskStatus.PLANNING
    remote_task_id: str | None = None


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str
    project_id: int
    codebase_id: int
    status: TaskStatus = TaskStatus.PLANNING
    remote_task_id: str | None = None


class TaskCreateNested(BaseModel):
    """Schema for creating a new task under a project (project_id from URL)."""

    title: str
    codebase_id: int
    remote_task_id: str | None = None
    specification_content: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    custom_fields: dict[str, Any] | None = None


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: str | None = None
    status: TaskStatus | None = None
    codebase_id: int | None = None
    remote_task_id: str | None = None
    conversation_id: str | None = None
    specification: str | None = None
    implementation_plan: str | None = None
    custom_fields: dict[str, Any] | None = None


class WorkflowActionInfo(BaseModel):
    """Schema for available workflow action information."""

    key: str
    label: str


class TaskResponse(TaskBase):
    """Schema for task responses."""

    id: int
    conversation_id: int
    created_at: datetime.datetime

    # Document IDs - content fetched separately via /api/documents/{id}
    specification_document_id: int
    implementation_plan_document_id: int | None = None
    change_summary_document_id: int | None = None

    # Custom field values
    custom_fields: dict[str, Any] | None = None

    # Available workflow actions based on current state
    available_workflow_actions: list[WorkflowActionInfo] = []

    model_config = {"from_attributes": True}


class StateTransitionRequest(BaseModel):
    """Schema for manual state transitions."""

    new_state: TaskStatus  # 'Designing', 'Planning', 'Implementing'


class CommitMetadata(BaseModel):
    """Lightweight schema for commit metadata (no file diffs)."""

    commit_hash: str
    author: str
    date: str
    message: str


class TaskBranchInfo(BaseModel):
    """Schema for task branch information.

    Used to populate UI dropdowns with commit list and uncommitted status.
    """

    commits: list[CommitMetadata]
    has_uncommitted_changes: bool


class FileDiff(BaseModel):
    """Schema for a single file's diff information."""

    file_path: str
    diff_content: str
    additions: int
    deletions: int
    is_new_file: bool = False
    is_deleted: bool = False


class TaskDiffResponse(BaseModel):
    """Schema for task git diff response.

    Returns a flat list of files with diffs for the requested view
    (all changes, uncommitted only, or specific commit).
    """

    files: list[FileDiff]
    additions: int
    deletions: int
    generated_at: datetime.datetime


class TaskGitStatusResponse(BaseModel):
    """Schema for task git status response."""

    branch_name: str | None
    branch_exists: bool
    base_branch: str
    commits_ahead: int
    commits_behind: int
    can_merge: bool
    has_conflicts: bool
    # New fields for branch status modal
    worktree_slot_path: str | None = None
    main_repo_is_clean: bool = True
    main_repo_current_branch: str | None = None
    # Rebase state
    rebase_in_progress: bool = False


class MergeBranchRequest(BaseModel):
    """Schema for merging a task branch."""

    target_branch: str | None = None
    delete_branch: bool = False


class MergeBranchResponse(BaseModel):
    """Schema for merge branch response."""

    success: bool
    merge_commit: str
    message: str


class RebaseBranchResponse(BaseModel):
    """Schema for rebase branch response."""

    success: bool
    new_head: str
    message: str


class CheckoutToMainResponse(BaseModel):
    """Schema for checkout-to-main response."""

    success: bool
    message: str


class GitHubPRStatusResponse(BaseModel):
    """Schema for GitHub PR status response.

    Used by the frontend to enable/disable merge actions and display PR status.
    """

    merged: bool
    mergeable: bool | None
    mergeable_state: str
    state: str
    review_comments_count: int
    checks_status: str | None
    pr_url: str
