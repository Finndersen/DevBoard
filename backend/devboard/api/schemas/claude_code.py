"""API schemas for the Claude Code session viewer endpoints."""

from datetime import datetime

from pydantic import BaseModel


class ClaudeCodeProjectResponse(BaseModel):
    path: str
    encoded_path: str
    last_activity: datetime | None
    last_cost: float | None
    last_lines_added: int | None
    last_lines_removed: int | None
    session_count: int


class ClaudeCodeSessionResponse(BaseModel):
    session_id: str
    label: str
    last_activity: datetime
    file_size: int
    is_empty: bool
    linked_session_id: str | None = None
    session_role: str | None = None


class SessionSearchResultResponse(BaseModel):
    session_id: str
    project_encoded_path: str
    line_number: int
    line_content: str
    message_uuid: str | None = None
    text_snippet: str | None = None
