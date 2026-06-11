"""Task Pydantic schemas."""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from devboard.db.models.task import TaskStatus


class TaskBase(BaseModel):
    """Base task schema."""

    title: str
    project_id: int
    codebase_id: int
    status: TaskStatus = TaskStatus.PLANNING


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str
    project_id: int
    codebase_id: int
    status: TaskStatus = TaskStatus.PLANNING


class TaskCreateNested(BaseModel):
    """Schema for creating a new task under a project (project_id from URL)."""

    title: str | None = None
    codebase_id: int
    specification_content: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    custom_fields: dict[str, Any] | None = None
    initial_message: str | None = None
    model_type: Literal["fast", "standard", "advanced", "auto"] | None = None

    @model_validator(mode="after")
    def validate_title_or_initial_message(self):
        """Validate that at least one of title or initial_message is provided."""
        if self.title is None and self.initial_message is None:
            raise ValueError("Either title or initial_message must be provided")
        return self


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: str | None = None
    status: TaskStatus | None = None
    codebase_id: int | None = None
    conversation_id: str | None = None
    specification: str | None = None
    implementation_plan: str | None = None
    custom_fields: dict[str, Any] | None = None


class WorkflowActionInfo(BaseModel):
    """Schema for available workflow action information."""

    key: str


class TaskListResponse(BaseModel):
    """Schema for task list responses (lightweight, no conversation/workflow data)."""

    id: int
    title: str
    project_id: int
    project_name: str
    codebase_id: int
    status: TaskStatus
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class TaskResponse(TaskBase):
    """Schema for task responses."""

    id: int
    conversation_id: int
    created_at: datetime.datetime

    # Document IDs - content fetched separately via /api/documents/{id}
    specification_document_id: int
    implementation_plan_document_id: int | None = None
    change_summary_document_id: int | None = None

    # Structured implementation plan ID (new model)
    implementation_plan_id: int | None = None

    # Custom field values
    custom_fields: dict[str, Any] | None = None

    # GitHub PR number (set when a PR is created for this task)
    github_pr_number: int | None = None

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

    pr_number: int
    pr_url: str
    title: str
    state: str
    merged: bool
    mergeable_state: str | None
    review_decision: str | None
    ci_status: str | None
    comment_count: int
    repo_full_name: str
    updated_at: datetime.datetime


class PRFeedbackCommentResponse(BaseModel):
    """A single PR review comment."""

    id: int
    author: str
    body: str
    path: str
    line: int | None
    diff_hunk: str | None
    created_at: datetime.datetime | None
    in_reply_to_id: int | None


class PRFeedbackCommentThreadResponse(BaseModel):
    """A thread of comments: original comment plus replies."""

    original: PRFeedbackCommentResponse
    replies: list[PRFeedbackCommentResponse]


class PRFeedbackReviewResponse(BaseModel):
    """A review with its associated comment threads."""

    id: int
    author: str
    state: str
    body: str
    submitted_at: datetime.datetime | None
    comment_threads: list[PRFeedbackCommentThreadResponse]


class PRFeedbackResponse(BaseModel):
    """Complete PR feedback including reviews and standalone comment threads."""

    reviews: list[PRFeedbackReviewResponse]
    standalone_threads: list[PRFeedbackCommentThreadResponse]
