"""Task-related database models."""

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, task_context_resource_association

if TYPE_CHECKING:
    from .codebase import Codebase
    from .configuration import ContextProviderResource
    from .document import Document
    from .project import Project
    from .worktree_slot import WorktreeSlot


class TaskStatus(StrEnum):
    """Enumeration of possible task statuses."""

    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    PR_OPEN = "pr_open"
    COMPLETE = "complete"


class Task(Base):
    """Represents a single, self-contained piece of work within a project."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    codebase_id: Mapped[int] = mapped_column(ForeignKey("codebases.id"))

    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PLANNING)
    # Git branch configuration
    branch_name: Mapped[str] = mapped_column(String(255))
    base_branch: Mapped[str] = mapped_column(String(255))

    # GitHub PR number (set when PR is created)
    github_pr_number: Mapped[int | None] = mapped_column(default=None)

    # Custom field values stored as JSON (e.g., {"jira_issue_id": "PROJ-123", "priority": "High"})
    custom_fields: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Document relationships
    specification_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    implementation_plan_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    change_summary_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    project: Mapped["Project"] = relationship(back_populates="tasks")
    codebase: Mapped["Codebase"] = relationship(back_populates="tasks")
    context_resources: Mapped[list["ContextProviderResource"]] = relationship(
        secondary=task_context_resource_association, back_populates="tasks"
    )
    worktree_slots: Mapped[list["WorktreeSlot"]] = relationship(
        foreign_keys="WorktreeSlot.last_used_by_task_id", back_populates="last_used_by_task"
    )

    # Document relationships (lazy loaded by default, use eager loading where needed)
    specification: Mapped["Document"] = relationship(
        foreign_keys=[specification_id],
    )
    implementation_plan: Mapped["Document | None"] = relationship(
        foreign_keys=[implementation_plan_id],
    )
    change_summary: Mapped["Document | None"] = relationship(
        foreign_keys=[change_summary_id],
    )

    @property
    def current_worktree_slot(self) -> "WorktreeSlot | None":
        """Get the currently locked worktree slot for this task.

        Returns:
            The WorktreeSlot that is currently locked by this task, or None if no slot is locked
        """
        return next((slot for slot in self.worktree_slots if slot.locked), None)

    def get_current_workspace_dir(self) -> str:
        """Get the workspace directory for this task, and raise exception if workspace is not allocated"""
        allocated_workspace = self.current_worktree_slot
        if not allocated_workspace:
            raise NoWorktreeAllocatedException("Workspace not allocated for task #{self.id}")
        return allocated_workspace.path

    # Valid status transitions: from_status -> set of allowed target statuses
    VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.PLANNING: {TaskStatus.IMPLEMENTING},
        TaskStatus.IMPLEMENTING: {TaskStatus.PR_OPEN, TaskStatus.COMPLETE},
        TaskStatus.PR_OPEN: {TaskStatus.COMPLETE},
        TaskStatus.COMPLETE: set(),
    }

    def verify_status_transition(self, target_status: TaskStatus) -> None:
        """Verify this task can transition to target status.

        Validates:
        1. The transition is allowed from the current status
        2. Required prerequisites exist for the target status

        Args:
            target_status: The target status to transition to

        Raises:
            InvalidStatusTransitionError: If the transition is not allowed or prerequisites are missing
        """
        # Check if transition is valid from current status
        allowed_targets = self.VALID_TRANSITIONS.get(self.status, set())
        if target_status not in allowed_targets:
            raise InvalidStatusTransitionError(f"Cannot transition from {self.status.value} to {target_status.value}")

        # Check prerequisites for target status
        if target_status == TaskStatus.IMPLEMENTING:
            if not self.implementation_plan or not self.implementation_plan.content.strip():
                raise InvalidStatusTransitionError("Cannot transition to IMPLEMENTING without implementation plan")


class NoWorktreeAllocatedException(Exception):
    """Raised when a task has no allocated worktree slot."""

    pass


class InvalidStatusTransitionError(Exception):
    """Raised when a task status transition is not valid."""

    pass
