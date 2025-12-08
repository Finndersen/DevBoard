"""Codebase-related database models."""

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, project_codebase_association

if TYPE_CHECKING:
    from .project import Project
    from .task import Task
    from .worktree_slot import WorktreeSlot


class MergeStrategy(StrEnum):
    """Strategy for merging feature branches back into base branches."""

    GITHUB_PR = "github_pr"  # Create a GitHub PR for external review and merge
    SQUASH = "squash"  # Squash all feature branch commits into a single commit
    REBASE = "rebase"  # Rebase feature branch onto base branch (linear history)
    MERGE_COMMIT = "merge_commit"  # Standard merge with a merge commit
    NONE = "none"  # DevBoard does not perform any git operations (manual handling)


class Codebase(Base):
    """Represents a software codebase that can be associated with projects and tasks."""

    __tablename__ = "codebases"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(Text)
    repository_url: Mapped[str | None] = mapped_column(String(512))
    local_path: Mapped[str] = mapped_column(String(512))
    default_branch: Mapped[str] = mapped_column(String(255), default="origin/main")
    merge_strategy: Mapped[str] = mapped_column(String(50), default=MergeStrategy.SQUASH.value)

    projects: Mapped[list["Project"]] = relationship(secondary=project_codebase_association, back_populates="codebases")
    tasks: Mapped[list["Task"]] = relationship(back_populates="codebase")
    worktree_slots: Mapped[list["WorktreeSlot"]] = relationship(back_populates="codebase")
