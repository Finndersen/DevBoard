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
    from .task import Task


class Project(Base):
    """Represents a high-level project or initiative (sub-project with a parent).

    A top-level project has `parent_project_id = None`.
    An initiative has `parent_project_id` pointing to its parent project.
    Max nesting depth is 1 (initiatives cannot have child initiatives).
    """

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

    # Hierarchy: optional parent project (makes this an initiative)
    parent_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)

    # Marks project/initiative as done and archives it from active views
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
    # Self-referential parent relationship (many-to-one): always eager-loaded so
    # parent_project_name is accessible without extra queries.
    parent: Mapped["Project | None"] = relationship(
        "Project",
        foreign_keys=[parent_project_id],
        remote_side="Project.id",
        back_populates="initiatives",
        lazy="joined",
    )
    # Self-referential children relationship (one-to-many)
    initiatives: Mapped[list["Project"]] = relationship(
        "Project",
        foreign_keys="[Project.parent_project_id]",
        back_populates="parent",
    )

    @property
    def parent_project_name(self) -> str | None:
        return self.parent.name if self.parent else None

    @property
    def is_initiative(self) -> bool:
        """True when this project is an initiative (nested under a parent project)."""
        return self.parent_project_id is not None
