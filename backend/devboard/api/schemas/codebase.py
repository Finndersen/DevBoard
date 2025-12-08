"""Codebase Pydantic schemas."""

from enum import StrEnum

from pydantic import BaseModel


class MergeStrategyEnum(StrEnum):
    """API enum for merge strategy options."""

    GITHUB_PR = "github_pr"
    SQUASH = "squash"
    REBASE = "rebase"
    MERGE_COMMIT = "merge_commit"
    NONE = "none"


class CodebaseBase(BaseModel):
    """Base codebase schema."""

    name: str
    description: str
    repository_url: str | None = None
    local_path: str
    default_branch: str
    merge_strategy: MergeStrategyEnum


class CodebaseCreate(BaseModel):
    """Schema for creating a new codebase."""

    name: str
    description: str
    local_path: str
    default_branch: str | None = None
    merge_strategy: MergeStrategyEnum | None = None  # Auto-determined if not provided


class CodebaseUpdate(BaseModel):
    """Schema for updating a codebase."""

    name: str | None = None
    description: str | None = None
    repository_url: str | None = None
    local_path: str | None = None
    default_branch: str | None = None
    merge_strategy: MergeStrategyEnum | None = None


class CodebaseResponse(CodebaseBase):
    """Schema for codebase responses."""

    id: int

    model_config = {"from_attributes": True}
