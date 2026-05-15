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
    setup_command: str | None = None
    developer_context: str | None = None


class CodebaseCommonOptions(BaseModel):
    """Common optional settings shared across all codebase creation modes."""

    description: str | None = None
    default_branch: str | None = None
    merge_method: MergeMethod | None = None  # Defaults to SQUASH
    branch_handling: BranchHandling | None = None  # Auto-determined from remote URL if not provided
    max_worktrees: int | None = None
    setup_command: str | None = None
    developer_context: str | None = None


class CodebaseCreate(CodebaseCommonOptions):
    """Schema for creating a new codebase from an existing local directory."""

    name: str
    description: str
    local_path: str


class CodebaseClone(CodebaseCommonOptions):
    """Schema for cloning a remote repository as a new codebase."""

    repository_url: str
    parent_directory: str
    name: str | None = None


class CodebaseInit(CodebaseCommonOptions):
    """Schema for initialising a new git project as a codebase."""

    name: str
    directory: str


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
    setup_command: str | None = None
    developer_context: str | None = None


class CodebaseResponse(CodebaseBase):
    """Schema for codebase responses."""

    id: int

    model_config = {"from_attributes": True}
