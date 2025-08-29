"""Base database models and shared components."""
import datetime
from typing import List, Optional

from sqlalchemy import Column, ForeignKey, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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