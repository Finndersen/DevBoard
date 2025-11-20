"""Task-related database models."""

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, task_context_resource_association

if TYPE_CHECKING:
    from .codebase import Codebase
    from .configuration import ContextProviderResource
    from .document import Document
    from .project import Project


class TaskStatus(StrEnum):
    """Enumeration of possible task statuses."""

    DEFINING = "defining"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    COMPLETE = "complete"


class Task(Base):
    """Represents a single, self-contained piece of work within a project."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    codebase_id: Mapped[int] = mapped_column(ForeignKey("codebases.id"))

    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.DEFINING)
    remote_task_id: Mapped[str | None] = mapped_column(String(100))

    # Git branch configuration
    branch_name: Mapped[str | None] = mapped_column(String(255))
    base_branch: Mapped[str] = mapped_column(String(255))

    # Document relationships
    specification_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    implementation_plan_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    project: Mapped["Project"] = relationship(back_populates="tasks")
    codebase: Mapped["Codebase"] = relationship(back_populates="tasks")
    context_resources: Mapped[list["ContextProviderResource"]] = relationship(
        secondary=task_context_resource_association, back_populates="tasks"
    )

    # Document relationships with eager loading
    specification: Mapped["Document"] = relationship(
        foreign_keys=[specification_id],
        lazy="joined",  # Always eager load
    )
    implementation_plan: Mapped["Document | None"] = relationship(
        foreign_keys=[implementation_plan_id],
        lazy="joined",  # Always eager load
    )

    def can_transition_to_phase(self, target_status: TaskStatus) -> tuple[bool, str]:
        """Check if this task can transition to target phase.

        Validates that required content exists before allowing phase transition.
        Each phase has specific prerequisites:
        - PLANNING: Requires specification content
        - IMPLEMENTING: Requires implementation plan
        - REVIEWING: Implementation must be marked complete
        - COMPLETE: All work must be finished

        Args:
            target_status: The target status to transition to

        Returns:
            Tuple of (can_transition, error_message)
            - can_transition: True if transition is allowed
            - error_message: Empty string if allowed, error description otherwise
        """
        # DEFINING → PLANNING
        if target_status == TaskStatus.PLANNING:
            if not self.specification or not self.specification.content.strip():
                return False, "Cannot transition to PLANNING without specification content"

        # PLANNING → IMPLEMENTING
        elif target_status == TaskStatus.IMPLEMENTING:
            if not self.implementation_plan or not self.implementation_plan.content.strip():
                return False, "Cannot transition to IMPLEMENTING without implementation plan"

        # IMPLEMENTING → REVIEWING
        elif target_status == TaskStatus.REVIEWING:
            # Could add checks for implementation completion markers
            # For now, allow transition if explicitly requested
            pass

        # REVIEWING → COMPLETE
        elif target_status == TaskStatus.COMPLETE:
            # Could add checks for review completion
            # For now, allow transition if explicitly requested
            pass

        # DEFINING is initial state, always allowed
        elif target_status == TaskStatus.DEFINING:
            pass

        return True, ""
