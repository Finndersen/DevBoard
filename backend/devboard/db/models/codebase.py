"""Codebase-related database models."""

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, project_codebase_association

if TYPE_CHECKING:
    from .project import Project
    from .task import Task


class Codebase(Base):
    """Represents a software codebase that can be associated with projects and tasks."""

    __tablename__ = "codebases"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    repository_url: Mapped[str | None] = mapped_column(String(512))
    local_path: Mapped[str] = mapped_column(String(512))

    projects: Mapped[list["Project"]] = relationship(
        secondary=project_codebase_association, back_populates="codebases"
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="codebase")
