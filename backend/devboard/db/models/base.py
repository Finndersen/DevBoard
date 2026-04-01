"""Base database models and shared components."""

import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Table
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime.datetime]):
    """DateTime type that always returns timezone-aware UTC datetimes.

    The DB stores naive datetimes (all written as UTC), so on read we
    reattach UTC tzinfo to make the Python objects unambiguous.
    """

    impl = DateTime
    cache_ok = True

    def process_result_value(self, value: datetime.datetime | None, dialect: object) -> datetime.datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=datetime.UTC)
        return value


class Base(DeclarativeBase):
    """Base class for all database models."""

    type_annotation_map = {
        datetime.datetime: UTCDateTime,
    }


# Association table for the many-to-many relationship between Projects and Codebases
project_codebase_association = Table(
    "project_codebase_association",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
    Column("codebase_id", ForeignKey("codebases.id"), primary_key=True),
)
