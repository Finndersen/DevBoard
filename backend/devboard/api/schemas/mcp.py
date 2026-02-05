"""MCP server management API schemas."""

from typing import Any

from pydantic import BaseModel


class MCPToolInfo(BaseModel):
    """Information about an MCP tool."""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None


class VerifyResult(BaseModel):
    """Result of verifying an MCP server connection."""

    success: bool
    tools: list[MCPToolInfo] | None = None
    error: str | None = None
