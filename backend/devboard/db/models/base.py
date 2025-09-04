"""Base database models and shared components."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Table
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# Association table for the many-to-many relationship between Projects and Codebases
project_codebase_association = Table(
    "project_codebase_association",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
    Column("codebase_id", ForeignKey("codebases.id"), primary_key=True),
)

# Association table for the many-to-many relationship between Projects and ContextProviderResources
project_context_resource_association = Table(
    "project_context_resources",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id"), primary_key=True),
    Column("resource_id", Integer, ForeignKey("context_provider_resources.id"), primary_key=True),
    Column(
        "added_at",
        DateTime,
        default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    ),
)

# Association table for the many-to-many relationship between Tasks and ContextProviderResources
task_context_resource_association = Table(
    "task_context_resources",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("resource_id", Integer, ForeignKey("context_provider_resources.id"), primary_key=True),
    Column(
        "added_at",
        DateTime,
        default=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    ),
)
