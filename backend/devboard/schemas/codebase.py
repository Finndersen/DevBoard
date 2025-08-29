"""Codebase Pydantic schemas."""
from typing import Optional

from pydantic import BaseModel


class CodebaseBase(BaseModel):
    """Base codebase schema."""
    name: str
    description: str
    repository_url: Optional[str] = None
    local_path: Optional[str] = None


class CodebaseCreate(CodebaseBase):
    """Schema for creating a new codebase."""
    pass


class CodebaseUpdate(BaseModel):
    """Schema for updating a codebase."""
    name: Optional[str] = None
    description: Optional[str] = None
    repository_url: Optional[str] = None
    local_path: Optional[str] = None


class CodebaseResponse(CodebaseBase):
    """Schema for codebase responses."""
    id: int

    model_config = {"from_attributes": True}