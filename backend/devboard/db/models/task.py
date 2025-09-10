"""Task-related database models."""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, task_context_resource_association

if TYPE_CHECKING:
    from .configuration import ContextProviderResource
    from .document import Document
    from .project import Project


class Task(Base):
    """Represents a single, self-contained piece of work within a project."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    codebase_id: Mapped[int | None] = mapped_column(ForeignKey("codebases.id"))

    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="Pending")
    remote_task_id: Mapped[str | None] = mapped_column(String(100))
    conversation_id: Mapped[str | None] = mapped_column(String(100))

    # Document relationships
    specification_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    implementation_plan_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    project: Mapped["Project"] = relationship(back_populates="tasks")
    codebase: Mapped["Codebase | None"] = relationship(back_populates="tasks")
    context_resources: Mapped[list["ContextProviderResource"]] = relationship(
        secondary=task_context_resource_association, back_populates="tasks"
    )
    messages: Mapped[list["TaskConversationMessage"]] = relationship(back_populates="task")

    # Document relationships with eager loading
    specification: Mapped["Document"] = relationship(
        foreign_keys=[specification_id],
        lazy="joined"  # Always eager load
    )
    implementation_plan: Mapped["Document | None"] = relationship(
        foreign_keys=[implementation_plan_id],
        lazy="joined"  # Always eager load
    )


