"""LogEntry-related database models."""

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .project import Project
    from .task import Task


class LogEntrySource(StrEnum):
    """Source of a log entry."""

    DEVELOPER = "developer"
    SYSTEM = "system"
    AGENT = "agent"


class LogEntryStatus(StrEnum):
    """Status of a log entry."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


class LogEntry(Base):
    """An append-only entry in the log entry stream, scoped to a project and/or task."""

    __tablename__ = "log_entries"
    __table_args__ = (
        Index("ix_log_entries_project_id", "project_id"),
        Index("ix_log_entries_task_id", "task_id"),
        Index("ix_log_entries_timestamp", "timestamp"),
        Index("ix_log_entries_type", "type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
    source: Mapped[LogEntrySource] = mapped_column(Enum(LogEntrySource))
    type: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    entry_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)

    status: Mapped[LogEntryStatus] = mapped_column(Enum(LogEntryStatus), default=LogEntryStatus.ACTIVE)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    project: Mapped["Project | None"] = relationship()
    task: Mapped["Task | None"] = relationship()
