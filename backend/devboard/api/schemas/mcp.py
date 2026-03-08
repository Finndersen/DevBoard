"""MCP server management API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, computed_field

from devboard.db.models.mcp_server import HttpMCPConfig, MCPServerType, StdioMCPConfig


class MCPToolInfo(BaseModel):
    """Information about an MCP tool (from server response)."""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None


class MCPToolResponse(BaseModel):
    """Response schema for a cached MCP tool."""

    id: int
    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None

    @computed_field
    @property
    def parameter_count(self) -> int:
        if not self.input_schema:
            return 0
        properties = self.input_schema.get("properties", {})
        return len(properties) if isinstance(properties, dict) else 0

    model_config = {"from_attributes": True}


class MCPToolUpdate(BaseModel):
    """Schema for updating an MCP tool."""

    description: str | None = None


class OAuthStatusResponse(BaseModel):
    """OAuth authentication status for an MCP server."""

    has_tokens: bool
    token_expired: bool
    has_client_info: bool


class MCPServerDetailResponse(BaseModel):
    """Response schema for MCP server detail including tools and verification status."""

    id: int
    name: str
    server_type: MCPServerType
    config_json: StdioMCPConfig | HttpMCPConfig
    last_verified_at: datetime | None = None
    last_verified_success: bool | None = None
    last_verified_error: str | None = None
    tools: list[MCPToolResponse] = []
    oauth_status: OAuthStatusResponse | None = None

    model_config = {"from_attributes": True}


class VerifyResult(BaseModel):
    """Result of verifying an MCP server connection."""

    success: bool
    tools: list[MCPToolInfo] | None = None
    error: str | None = None


class MCPToolRunRequest(BaseModel):
    """Request schema for running an MCP tool."""

    arguments: dict[str, Any] | None = None


class MCPToolRunResponse(BaseModel):
    """Response schema for MCP tool execution result."""

    success: bool
    result: str | None = None
    error: str | None = None
