"""Task Pydantic schemas."""

import datetime

from pydantic import BaseModel

from devboard.db.models.task import TaskStatus

from .document import DocumentResponse


class TaskBase(BaseModel):
    """Base task schema."""

    title: str
    project_id: int
    codebase_id: int | None = None
    status: TaskStatus = TaskStatus.DEFINING
    remote_task_id: str | None = None


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str
    project_id: int
    codebase_id: int | None = None
    status: TaskStatus = TaskStatus.DEFINING
    remote_task_id: str | None = None


class TaskCreateNested(BaseModel):
    """Schema for creating a new task under a project (project_id from URL)."""

    title: str
    codebase_id: int | None = None
    status: TaskStatus = TaskStatus.DEFINING
    remote_task_id: str | None = None


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: str | None = None
    status: TaskStatus | None = None
    remote_task_id: str | None = None
    conversation_id: str | None = None
    specification: str | None = None
    implementation_plan: str | None = None


class TaskResponse(TaskBase):
    """Schema for task responses."""

    id: int
    conversation_id: str | None = None
    default_conversation_id: int | None = None
    created_at: datetime.datetime

    # Document relationships - automatically loaded
    specification: DocumentResponse
    implementation_plan: DocumentResponse | None = None

    model_config = {"from_attributes": True}


class StateTransitionRequest(BaseModel):
    """Schema for manual state transitions."""

    new_state: TaskStatus  # 'Designing', 'Planning', 'Implementing'
