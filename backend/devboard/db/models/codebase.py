"""Codebase-related database models."""

from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, project_codebase_association
from .enums import EntityType

if TYPE_CHECKING:
    from .project import Project
    from .task import Task
    from .worktree_slot import WorktreeSlot


class MergeMethod(StrEnum):
    """How commits are combined during merge."""

    SQUASH = "squash"  # Squash all feature branch commits into a single commit
    REBASE = "rebase"  # Rebase feature branch onto base branch (linear history)
    MERGE_COMMIT = "merge_commit"  # Standard merge with a merge commit


class BranchHandling(StrEnum):
    """Where/how the feature branch is finalized."""

    LOCAL_MERGE = "local_merge"  # Merge locally using merge_method
    GITHUB_PR = "github_pr"  # Create PR on GitHub, merge via GitHub using merge_method
    MANUAL = "manual"  # No automatic handling - user manages branch manually


# Backwards compatibility alias (deprecated)
MergeStrategy = MergeMethod


class Codebase(Base):
    """Represents a software codebase that can be associated with projects and tasks."""

    __tablename__ = "codebases"
    entity_type: ClassVar[EntityType] = EntityType.CODEBASE

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(Text)
    repository_url: Mapped[str | None] = mapped_column(String(512))
    local_path: Mapped[str] = mapped_column(String(512))
    default_branch: Mapped[str] = mapped_column(String(255), default="origin/main")
    merge_method: Mapped[str] = mapped_column(String(50), default=MergeMethod.SQUASH.value)
    branch_handling: Mapped[str] = mapped_column(String(50), default=BranchHandling.LOCAL_MERGE.value)
    max_worktrees: Mapped[int | None] = mapped_column(default=None)
    setup_command: Mapped[str | None] = mapped_column(String(1024), default=None)
    developer_context: Mapped[str | None] = mapped_column(Text, default=None)

    projects: Mapped[list["Project"]] = relationship(secondary=project_codebase_association, back_populates="codebases")
    tasks: Mapped[list["Task"]] = relationship(back_populates="codebase")
    worktree_slots: Mapped[list["WorktreeSlot"]] = relationship(back_populates="codebase")
