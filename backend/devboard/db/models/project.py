"""Project-related database models."""

import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import (
    Base,
    project_codebase_association,
)

if TYPE_CHECKING:
    from .codebase import Codebase
    from .document import Document
    from .task import Task


class Project(Base):
    """Represents a high-level project, which can have associated tasks and codebases."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(300))

    # Custom field values stored as JSON (e.g., {"jira_project_id": "PROJ", "team": "Backend"})
    custom_fields: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Document relationship
    specification_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
    codebases: Mapped[list["Codebase"]] = relationship(
        secondary=project_codebase_association, back_populates="projects"
    )
    # Document relationship with eager loading
    specification: Mapped["Document"] = relationship(
        foreign_keys=[specification_document_id],
        lazy="joined",  # Always eager load
        cascade="all, delete-orphan",
        single_parent=True,
    )
