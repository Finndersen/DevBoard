"""Task Pydantic schemas."""

import datetime

from pydantic import BaseModel


class TaskBase(BaseModel):
    """Base task schema."""

    title: str
    description: str | None = None
    project_id: int
    codebase_id: int | None = None
    status: str = "Pending"
    remote_task_id: str | None = None


class TaskCreate(TaskBase):
    """Schema for creating a new task."""

    pass


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: str | None = None
    description: str | None = None
    status: str | None = None
    remote_task_id: str | None = None
    conversation_id: str | None = None
    implementation_plan: str | None = None


class TaskResponse(TaskBase):
    """Schema for task responses."""

    id: int
    conversation_id: str | None = None
    implementation_plan: str | None = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
