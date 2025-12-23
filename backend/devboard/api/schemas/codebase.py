"""Codebase Pydantic schemas."""

from pydantic import BaseModel

from devboard.db.models.codebase import MergeStrategy


class CodebaseBase(BaseModel):
    """Base codebase schema."""

    name: str
    description: str
    repository_url: str | None = None
    local_path: str
    default_branch: str
    merge_strategy: MergeStrategy
    max_worktrees: int | None = None


class CodebaseCreate(BaseModel):
    """Schema for creating a new codebase."""

    name: str
    description: str
    local_path: str
    default_branch: str | None = None
    merge_strategy: MergeStrategy | None = None  # Auto-determined if not provided
    max_worktrees: int | None = None


class CodebaseUpdate(BaseModel):
    """Schema for updating a codebase."""

    name: str | None = None
    description: str | None = None
    repository_url: str | None = None
    local_path: str | None = None
    default_branch: str | None = None
    merge_strategy: MergeStrategy | None = None
    max_worktrees: int | None = None


class CodebaseResponse(CodebaseBase):
    """Schema for codebase responses."""

    id: int

    model_config = {"from_attributes": True}
