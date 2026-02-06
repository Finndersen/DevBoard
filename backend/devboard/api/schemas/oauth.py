"""OAuth Pydantic schemas."""

from pydantic import BaseModel

from devboard.db.models.mcp_server import HttpMCPConfig, MCPServerType, StdioMCPConfig

# MCP Server Config schemas


class MCPServerConfigCreate(BaseModel):
    """Schema for creating an MCP server configuration."""

    name: str
    server_type: MCPServerType
    config_json: StdioMCPConfig | HttpMCPConfig


class MCPServerConfigUpdate(BaseModel):
    """Schema for updating an MCP server configuration."""

    name: str | None = None
    server_type: MCPServerType | None = None
    config_json: StdioMCPConfig | HttpMCPConfig | None = None


class MCPServerConfigResponse(BaseModel):
    """Schema for MCP server configuration responses."""

    id: int
    name: str
    server_type: MCPServerType
    config_json: StdioMCPConfig | HttpMCPConfig
    last_verified_at: str | None = None
    last_verified_success: bool | None = None
    last_verified_error: str | None = None

    model_config = {"from_attributes": True}


# OAuth Callback schemas


class OAuthCallbackQueryParams(BaseModel):
    """Query parameters for OAuth callback endpoint.

    These parameters are defined by the OAuth 2.0 specification.
    Either (code, state) or (error, error_description) will be present.
    """

    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None


class OAuthCallbackResponse(BaseModel):
    """Schema for OAuth callback responses."""

    success: bool
    message: str
    provider_key: str


class OAuthCallbackError(BaseModel):
    """Schema for OAuth callback error responses."""

    success: bool = False
    error: str
    provider_key: str
