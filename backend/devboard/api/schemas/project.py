"""Project Pydantic schemas."""

import datetime

from pydantic import BaseModel

from .document import DocumentResponse


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str
    current_status: str


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str
    current_status: str = ""


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: str | None = None
    current_status: str | None = None


class ProjectResponse(ProjectBase):
    """Schema for project responses."""

    id: int
    created_at: datetime.datetime
    
    # Document relationship - automatically loaded
    details: DocumentResponse

    model_config = {"from_attributes": True}
