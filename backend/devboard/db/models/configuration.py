"""Configuration-related database models."""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, project_context_resource_association, task_context_resource_association

if TYPE_CHECKING:
    from .project import Project
    from .task import Task


class Configuration(Base):
    """Generic key-value configuration store for all application settings."""

    __tablename__ = "configurations"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String(50), default="1.0")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC)
    )


class ContextProviderResource(Base):
    """Represents a context provider resource that can be shared across projects and tasks."""

    __tablename__ = "context_provider_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(255))  # References context provider by name
    resource_uri: Mapped[str] = mapped_column(String(1024), unique=True)  # Enforce uniqueness
    description: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    # M2M relationships
    projects: Mapped[list["Project"]] = relationship(
        secondary=project_context_resource_association, back_populates="context_resources"
    )
    tasks: Mapped[list["Task"]] = relationship(
        secondary=task_context_resource_association, back_populates="context_resources"
    )
