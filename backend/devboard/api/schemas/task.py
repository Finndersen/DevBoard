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


class TaskCreate(BaseModel):
    """Schema for creating a new task."""

    title: str
    description: str | None = None
    project_id: int
    codebase_id: int | None = None
    status: str = "Pending"
    remote_task_id: str | None = None


class TaskCreateNested(BaseModel):
    """Schema for creating a new task under a project (project_id from URL)."""

    title: str
    description: str | None = None
    codebase_id: int | None = None
    status: str = "Pending"
    remote_task_id: str | None = None


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


# Task Planning Agent Schemas


class DocumentEdit(BaseModel):
    """Schema for a single document edit."""

    find: str
    replace: str


class TaskPlanningResponse(BaseModel):
    """Schema for Task Planning Agent structured response."""

    message: str
    task_specification_edits: list[DocumentEdit] | None = None
    task_implementation_plan_edits: list[DocumentEdit] | None = None


class TaskConversationMessage(BaseModel):
    """Schema for task conversation message."""

    id: int
    task_id: int
    role: str  # 'user', 'assistant', 'tool_call', 'tool_result'
    content: str | None = None
    tool_data: dict | None = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class TaskPlanningRequest(BaseModel):
    """Schema for sending message to task planning agent."""

    message: str


class ApplyEditsRequest(BaseModel):
    """Schema for applying document edits from agent."""

    message_id: int
    task_specification_edits: list[DocumentEdit] | None = None
    task_implementation_plan_edits: list[DocumentEdit] | None = None


class StateTransitionRequest(BaseModel):
    """Schema for manual state transitions."""

    new_state: str  # 'Designing', 'Planning', 'Implementing'
