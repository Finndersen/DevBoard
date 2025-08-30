"""Base database models and shared components."""

from sqlalchemy import Column, ForeignKey, Table
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
