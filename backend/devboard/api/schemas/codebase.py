"""Codebase Pydantic schemas."""

from pydantic import BaseModel

from devboard.db.models.codebase import BranchHandling, MergeMethod


class CodebaseBase(BaseModel):
    """Base codebase schema."""

    name: str
    description: str
    repository_url: str | None = None
    local_path: str
    default_branch: str
    merge_method: MergeMethod
    branch_handling: BranchHandling
    max_worktrees: int | None = None


class CodebaseCreate(BaseModel):
    """Schema for creating a new codebase."""

    name: str
    description: str
    local_path: str
    default_branch: str | None = None
    merge_method: MergeMethod | None = None  # Defaults to SQUASH
    branch_handling: BranchHandling | None = None  # Auto-determined based on repository_url if not provided
    max_worktrees: int | None = None


class CodebaseUpdate(BaseModel):
    """Schema for updating a codebase."""

    name: str | None = None
    description: str | None = None
    repository_url: str | None = None
    local_path: str | None = None
    default_branch: str | None = None
    merge_method: MergeMethod | None = None
    branch_handling: BranchHandling | None = None
    max_worktrees: int | None = None


class CodebaseResponse(CodebaseBase):
    """Schema for codebase responses."""

    id: int

    model_config = {"from_attributes": True}
