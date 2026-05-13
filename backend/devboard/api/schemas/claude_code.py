"""API schemas for the Claude Code session viewer endpoints."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class McpServerStatus(StrEnum):
    """MCP server connection status."""

    connected = "connected"
    needs_auth = "needs_auth"
    failed = "failed"


class McpServerType(StrEnum):
    """MCP server type."""

    remote = "remote"
    local = "local"


class McpServerResponse(BaseModel):
    """Response model for MCP server status."""

    name: str
    url_or_command: str
    status: McpServerStatus
    type: McpServerType


class ClaudeCodeProjectResponse(BaseModel):
    path: str
    encoded_path: str
    last_activity: datetime | None
    session_count: int


class SessionTaskInfoResponse(BaseModel):
    task_id: int
    task_title: str
    agent_role: str


class SubAgentInfoResponse(BaseModel):
    agent_role: str
    parent_task_id: int | None
    parent_task_title: str | None


class ClaudeCodeSessionResponse(BaseModel):
    session_id: str
    label: str
    last_activity: datetime
    start_time: datetime
    file_size: int
    is_empty: bool
    linked_session_id: str | None = None
    session_role: str | None = None
    task_info: SessionTaskInfoResponse | None = None
    sub_agent_info: SubAgentInfoResponse | None = None


class SessionLocateResponse(BaseModel):
    project_encoded_path: str


class SessionSearchResultResponse(BaseModel):
    session_id: str
    project_encoded_path: str
    line_number: int
    line_content: str
    message_uuid: str | None = None
    text_snippet: str | None = None
