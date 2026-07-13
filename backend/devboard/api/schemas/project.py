"""Project Pydantic schemas."""

import datetime
from typing import Any

from pydantic import BaseModel


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str
    description: str


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str
    description: str
    custom_fields: dict[str, Any] | None = None


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: str | None = None
    description: str | None = None
    specification: str | None = None
    custom_fields: dict[str, Any] | None = None
    complete: bool | None = None


class ProjectResponse(ProjectBase):
    """Schema for project responses."""

    id: int
    created_at: datetime.datetime
    default_conversation_id: int | None = None
    custom_fields: dict[str, Any] | None = None

    # Document ID - content fetched separately via /api/documents/{id}
    specification_document_id: int

    # Completion status
    complete: bool = False

    model_config = {"from_attributes": True}


class InitiativeCreate(BaseModel):
    """Schema for creating a new initiative."""

    name: str
    description: str


class InitiativeResponse(BaseModel):
    """Schema for initiative responses."""

    id: int
    name: str
    description: str
    project_id: int
    specification_document_id: int
    complete: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
