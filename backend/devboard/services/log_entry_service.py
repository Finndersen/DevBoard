"""Service for managing log entry stream operations.

Handles log entry creation with auto-population of project_id from task context,
plus thin passthroughs for querying and updating log entries.
"""

from datetime import datetime
from typing import Any

from fastapi import HTTPException

from devboard.db.models.log_entry import LogEntry, LogEntrySource, LogEntryStatus
from devboard.db.repositories.log_entry import LogEntryRepository
from devboard.db.repositories.task import TaskRepository


class LogEntryService:
    """Service for log entry stream operations."""

    def __init__(
        self,
        log_entry_repo: LogEntryRepository,
        task_repo: TaskRepository,
    ):
        self.log_entry_repo = log_entry_repo
        self.task_repo = task_repo

    def create_log_entry(
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
        """Create a new log entry, auto-populating project_id from task if needed.

        If task_id is provided but project_id is not, looks up the task and
        inherits its project_id. Raises HTTP 404 if the task does not exist.

        Args:
            source: Who produced the log entry (developer, system, agent)
            type: Slug identifier for the log entry type
            content: Human-readable description
            project_id: Optional FK to projects table
            task_id: Optional FK to tasks table
            entry_metadata: Optional structured payload
            status: Initial status (defaults to ACTIVE)
            pinned: Whether the log entry is pinned (defaults to False)
            timestamp: Optional explicit timestamp (defaults to now in repository)

        Returns:
            Created LogEntry instance
        """
        if task_id is not None and project_id is None:
            task = self.task_repo.get_by_id(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            project_id = task.project_id

        return self.log_entry_repo.create(
            source=source,
            type=type,
            content=content,
            project_id=project_id,
            task_id=task_id,
            entry_metadata=entry_metadata,
            status=status,
            pinned=pinned,
            timestamp=timestamp,
        )

    def query_log_entries(
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
        """Query log entries with optional filters."""
        return self.log_entry_repo.query(
            project_id=project_id,
            task_id=task_id,
            type_pattern=type_pattern,
            since=since,
            until=until,
            status=status,
            source=source,
            pinned=pinned,
            limit=limit,
            offset=offset,
        )

    def update_log_entry(
        self,
        log_entry_id: int,
        *,
        status: LogEntryStatus | None = None,
        pinned: bool | None = None,
    ) -> LogEntry | None:
        """Update mutable fields of a log entry (status and/or pinned) in a single operation."""
        return self.log_entry_repo.update(log_entry_id, status=status, pinned=pinned)

    def update_log_entry_status(self, log_entry_id: int, status: LogEntryStatus) -> LogEntry | None:
        """Update the status of a log entry."""
        return self.log_entry_repo.update_status(log_entry_id, status)

    def update_log_entry_pinned(self, log_entry_id: int, pinned: bool) -> LogEntry | None:
        """Update the pinned flag of a log entry."""
        return self.log_entry_repo.update_pinned(log_entry_id, pinned)
