"""Project-related database models."""

import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import (
    Base,
    project_codebase_association,
)
from .enums import EntityType

if TYPE_CHECKING:
    from .codebase import Codebase
    from .document import Document
    from .initiative import Initiative
    from .task import Task


class Project(Base):
    """Represents a high-level project containing tasks and initiatives."""

    __tablename__ = "projects"
    entity_type: ClassVar[EntityType] = EntityType.PROJECT

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(300))

    # Custom field values stored as JSON (e.g., {"jira_project_id": "PROJ", "team": "Backend"})
    custom_fields: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Document relationship
    specification_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    # Marks project as done and archives it from active views
    complete: Mapped[bool] = mapped_column(default=False)

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
    initiatives: Mapped[list["Initiative"]] = relationship(back_populates="project")
