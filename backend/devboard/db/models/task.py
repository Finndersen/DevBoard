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
    from .messages import TaskConversationMessage
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
    codebase_id: Mapped[int | None] = mapped_column(ForeignKey("codebases.id"))

    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.DEFINING)
    remote_task_id: Mapped[str | None] = mapped_column(String(100))

    # Document relationships
    specification_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    implementation_plan_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    project: Mapped["Project"] = relationship(back_populates="tasks")
    codebase: Mapped["Codebase | None"] = relationship(back_populates="tasks")
    context_resources: Mapped[list["ContextProviderResource"]] = relationship(
        secondary=task_context_resource_association, back_populates="tasks"
    )
    messages: Mapped[list["TaskConversationMessage"]] = relationship(back_populates="task")

    # Document relationships with eager loading
    specification: Mapped["Document"] = relationship(
        foreign_keys=[specification_id],
        lazy="joined",  # Always eager load
    )
    implementation_plan: Mapped["Document"] = relationship(
        foreign_keys=[implementation_plan_id],
        lazy="joined",  # Always eager load
    )
