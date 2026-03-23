"""LogEntry Pydantic schemas."""

import datetime
from typing import Any

from pydantic import BaseModel, model_validator

from devboard.db.models.log_entry import LogEntrySource, LogEntryStatus


class LogEntryCreate(BaseModel):
    """Schema for creating a new log entry."""

    type: str
    content: str
    source: LogEntrySource = LogEntrySource.DEVELOPER
    metadata: dict[str, Any] | None = None
    project_id: int | None = None
    task_id: int | None = None
    pinned: bool = False


class LogEntryResponse(BaseModel):
    """Schema for log entry responses."""

    id: int
    timestamp: datetime.datetime
    source: LogEntrySource
    type: str
    content: str
    metadata: dict[str, Any] | None
    project_id: int | None
    task_id: int | None
    status: LogEntryStatus
    pinned: bool


class LogEntryUpdate(BaseModel):
    """Schema for updating a log entry's mutable fields (status and/or pinned)."""

    status: LogEntryStatus | None = None
    pinned: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "LogEntryUpdate":
        if self.status is None and self.pinned is None:
            raise ValueError("At least one of 'status' or 'pinned' must be provided")
        return self
