"""Codebase Pydantic schemas."""

from pydantic import BaseModel


class CodebaseBase(BaseModel):
    """Base codebase schema."""

    name: str
    description: str
    repository_url: str | None = None
    local_path: str


class CodebaseCreate(BaseModel):
    """Schema for creating a new codebase."""

    name: str
    description: str
    local_path: str


class CodebaseUpdate(BaseModel):
    """Schema for updating a codebase."""

    name: str | None = None
    description: str | None = None
    repository_url: str | None = None
    local_path: str | None = None


class CodebaseResponse(CodebaseBase):
    """Schema for codebase responses."""

    id: int

    model_config = {"from_attributes": True}
