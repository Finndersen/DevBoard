"""Project Pydantic schemas."""

import datetime

from pydantic import BaseModel

from .document import DocumentResponse


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str
    description: str


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str
    description: str


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: str | None = None
    description: str | None = None
    specification: str | None = None


class ProjectResponse(ProjectBase):
    """Schema for project responses."""

    id: int
    created_at: datetime.datetime
    default_conversation_id: int | None = None

    # Document relationship - automatically loaded
    specification: DocumentResponse

    model_config = {"from_attributes": True}
