"""LogEntry repository for log entry stream data access operations."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from devboard.db.models.log_entry import LogEntry, LogEntrySource, LogEntryStatus
from devboard.db.repositories.base import BaseRepository


class LogEntryRepository(BaseRepository[LogEntry]):
    """Repository for log entry stream data access operations."""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def create(
        self,
        source: LogEntrySource,
        type: str,
        content: str,
        project_id: int | None = None,
        task_id: int | None = None,
        entry_metadata: dict[str, Any] | None = None,
        status: LogEntryStatus = LogEntryStatus.ACTIVE,
        pinned: bool = False,
        timestamp: datetime | None = None,
    ) -> LogEntry:
        """Create a new log entry in the stream.

        Does NOT auto-populate project_id from task_id — that is the service's responsibility.

        Args:
            source: Who produced the log entry (developer, system, agent)
            type: Slug identifier for the log entry type
            content: Human-readable description
            project_id: Optional FK to projects table
            task_id: Optional FK to tasks table
            entry_metadata: Optional structured payload
            status: Initial status (defaults to ACTIVE)
            pinned: Whether the log entry is pinned (defaults to False)
            timestamp: Optional explicit timestamp (defaults to now)

        Returns:
            Created LogEntry instance
        """
        kwargs: dict[str, Any] = {
            "source": source,
            "type": type,
            "content": content,
            "project_id": project_id,
            "task_id": task_id,
            "entry_metadata": entry_metadata,
            "status": status,
            "pinned": pinned,
        }
        if timestamp is not None:
            kwargs["timestamp"] = timestamp

        log_entry = LogEntry(**kwargs)
        self.db.add(log_entry)
        self.db.flush()
        return log_entry

    def get_by_id(self, log_entry_id: int) -> LogEntry | None:
        """Get a log entry by its primary key.

        Args:
            log_entry_id: The log entry ID to look up

        Returns:
            LogEntry instance if found, None otherwise
        """
        return self.db.execute(select(LogEntry).where(LogEntry.id == log_entry_id)).scalar_one_or_none()

    def query(
        self,
        *,
        project_id: int | None = None,
        task_id: int | None = None,
        type_pattern: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        status: LogEntryStatus | None = None,
        source: LogEntrySource | None = None,
        pinned: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[LogEntry]:
        """Query log entries with optional filters, ordered by timestamp descending.

        Args:
            project_id: Filter by project scope
            task_id: Filter by task scope
            type_pattern: Filter by log entry type; supports '*' as a wildcard
                          (e.g. "task.*" matches "task.created", "task.completed")
            since: Include only log entries at or after this datetime
            until: Include only log entries at or before this datetime
            status: Filter by log entry status
            source: Filter by log entry source
            pinned: Filter by pinned flag
            limit: Maximum number of results to return
            offset: Number of results to skip (for pagination)

        Returns:
            List of matching LogEntry instances ordered by timestamp descending
        """
        stmt = select(LogEntry)

        if project_id is not None:
            stmt = stmt.where(LogEntry.project_id == project_id)
        if task_id is not None:
            stmt = stmt.where(LogEntry.task_id == task_id)
        if type_pattern is not None:
            if "*" in type_pattern:
                sql_pattern = type_pattern.replace("*", "%")
                stmt = stmt.where(LogEntry.type.like(sql_pattern))
            else:
                stmt = stmt.where(LogEntry.type == type_pattern)
        if since is not None:
            stmt = stmt.where(LogEntry.timestamp >= since)
        if until is not None:
            stmt = stmt.where(LogEntry.timestamp <= until)
        if status is not None:
            stmt = stmt.where(LogEntry.status == status)
        if source is not None:
            stmt = stmt.where(LogEntry.source == source)
        if pinned is not None:
            stmt = stmt.where(LogEntry.pinned == pinned)

        stmt = stmt.order_by(LogEntry.timestamp.desc())

        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(self.db.execute(stmt).scalars().all())

    def update(
        self,
        log_entry_id: int,
        *,
        status: LogEntryStatus | None = None,
        pinned: bool | None = None,
    ) -> LogEntry | None:
        """Update mutable fields of a log entry in a single fetch.

        Returns the updated LogEntry, or None if not found.
        """
        log_entry = self.get_by_id(log_entry_id)
        if log_entry is None:
            return None
        if status is not None:
            log_entry.status = status
        if pinned is not None:
            log_entry.pinned = pinned
        self.db.flush()
        return log_entry

    def update_status(self, log_entry_id: int, status: LogEntryStatus) -> LogEntry | None:
        """Update the status of a log entry.

        Args:
            log_entry_id: The log entry ID to update
            status: The new status value

        Returns:
            Updated LogEntry instance or None if not found
        """
        log_entry = self.get_by_id(log_entry_id)
        if log_entry is None:
            return None
        log_entry.status = status
        self.db.flush()
        return log_entry

    def update_pinned(self, log_entry_id: int, pinned: bool) -> LogEntry | None:
        """Update the pinned flag of a log entry.

        Args:
            log_entry_id: The log entry ID to update
            pinned: The new pinned value

        Returns:
            Updated LogEntry instance or None if not found
        """
        log_entry = self.get_by_id(log_entry_id)
        if log_entry is None:
            return None
        log_entry.pinned = pinned
        self.db.flush()
        return log_entry
