"""Project-related database models."""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import (
    Base,
    project_codebase_association,
    project_context_resource_association,
)

if TYPE_CHECKING:
    from .codebase import Codebase
    from .configuration import ContextProviderResource
    from .document import Document
    from .messages import ProjectConversationMessage
    from .task import Task


class Project(Base):
    """Represents a high-level project, which can have associated tasks and codebases."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(300))

    # Document relationship
    specification_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
    codebases: Mapped[list["Codebase"]] = relationship(
        secondary=project_codebase_association, back_populates="projects"
    )
    context_resources: Mapped[list["ContextProviderResource"]] = relationship(
        secondary=project_context_resource_association, back_populates="projects"
    )
    messages: Mapped[list["ProjectConversationMessage"]] = relationship(back_populates="project")

    # Document relationship with eager loading
    specification: Mapped["Document"] = relationship(
        foreign_keys=[specification_document_id],
        lazy="joined",  # Always eager load
    )
