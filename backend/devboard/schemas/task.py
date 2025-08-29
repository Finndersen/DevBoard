"""Task Pydantic schemas."""
import datetime
from typing import Optional

from pydantic import BaseModel


class TaskBase(BaseModel):
    """Base task schema."""
    title: str
    description: Optional[str] = None
    project_id: int
    codebase_id: Optional[int] = None
    status: str = "Pending"
    remote_task_id: Optional[str] = None


class TaskCreate(TaskBase):
    """Schema for creating a new task."""
    pass


class TaskUpdate(BaseModel):
    """Schema for updating a task."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    remote_task_id: Optional[str] = None
    conversation_id: Optional[str] = None
    implementation_plan: Optional[str] = None


class TaskResponse(TaskBase):
    """Schema for task responses."""
    id: int
    conversation_id: Optional[str] = None
    implementation_plan: Optional[str] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}