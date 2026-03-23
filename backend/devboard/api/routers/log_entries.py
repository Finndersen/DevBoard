"""Log entry stream API endpoints."""

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from devboard.api.dependencies.services import get_log_entry_service
from devboard.api.schemas.log_entry import LogEntryCreate, LogEntryResponse, LogEntryUpdate
from devboard.db.models.log_entry import LogEntry, LogEntrySource, LogEntryStatus
from devboard.services.log_entry_service import LogEntryService

router = APIRouter()


def _log_entry_response(log_entry: LogEntry) -> LogEntryResponse:
    """Build a LogEntryResponse from a LogEntry ORM instance."""
    return LogEntryResponse(
        id=log_entry.id,
        timestamp=log_entry.timestamp,
        source=log_entry.source,
        type=log_entry.type,
        content=log_entry.content,
        metadata=log_entry.entry_metadata,
        project_id=log_entry.project_id,
        task_id=log_entry.task_id,
        status=log_entry.status,
        pinned=log_entry.pinned,
    )


@router.post("/", response_model=LogEntryResponse, status_code=201)
def create_log_entry(
    body: LogEntryCreate,
    log_entry_service: LogEntryService = Depends(get_log_entry_service),
) -> LogEntryResponse:
    """Create a new log entry in the log entry stream.

    If `task_id` is provided without `project_id`, the project is resolved
    automatically from the task's parent project.
    """
    log_entry = log_entry_service.create_log_entry(
        source=body.source,
        type=body.type,
        content=body.content,
        project_id=body.project_id,
        task_id=body.task_id,
        entry_metadata=body.metadata,
        pinned=body.pinned,
    )
    return _log_entry_response(log_entry)


@router.get("/", response_model=list[LogEntryResponse])
def query_log_entries(
    project_id: int | None = Query(None),
    task_id: int | None = Query(None),
    type: str | None = Query(None),
    since: datetime.datetime | None = Query(None),
    until: datetime.datetime | None = Query(None),
    status: LogEntryStatus | None = Query(None),
    source: LogEntrySource | None = Query(None),
    pinned: bool | None = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    log_entry_service: LogEntryService = Depends(get_log_entry_service),
) -> list[LogEntryResponse]:
    """Query log entries with optional filter parameters."""
    log_entries = log_entry_service.query_log_entries(
        project_id=project_id,
        task_id=task_id,
        type_pattern=type,
        since=since,
        until=until,
        status=status,
        source=source,
        pinned=pinned,
        limit=limit,
        offset=offset,
    )
    return [_log_entry_response(e) for e in log_entries]


@router.patch("/{log_entry_id}", response_model=LogEntryResponse)
def update_log_entry(
    log_entry_id: int,
    body: LogEntryUpdate,
    log_entry_service: LogEntryService = Depends(get_log_entry_service),
) -> LogEntryResponse:
    """Update mutable fields of a log entry (status and/or pinned).

    At least one of `status` or `pinned` must be provided.
    Returns 404 if the log entry does not exist.
    """
    log_entry = log_entry_service.update_log_entry(log_entry_id, status=body.status, pinned=body.pinned)
    if log_entry is None:
        raise HTTPException(status_code=404, detail=f"Log entry {log_entry_id} not found")
    return _log_entry_response(log_entry)
