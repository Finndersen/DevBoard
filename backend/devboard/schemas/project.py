"""Project Pydantic schemas."""
import datetime
from typing import Optional

from pydantic import BaseModel


class ProjectBase(BaseModel):
    """Base project schema."""
    name: str
    details: str
    current_status: str


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    name: Optional[str] = None
    details: Optional[str] = None
    current_status: Optional[str] = None


class ProjectResponse(ProjectBase):
    """Schema for project responses."""
    id: int
    created_at: datetime.datetime

    model_config = {"from_attributes": True}