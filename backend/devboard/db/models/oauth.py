"""OAuth-related database models."""

import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MCPServerType(StrEnum):
    """Enumeration of MCP server connection types."""

    STDIO = "stdio"
    HTTP = "http"


class OAuthProviderType(StrEnum):
    """Enumeration of supported OAuth provider types."""

    JIRA = "jira"
    SLACK = "slack"
    GITHUB = "github"


# Pydantic models for MCPServerConfig.config_json validation


class StdioMCPConfig(BaseModel):
    """Configuration for STDIO-based MCP servers."""

    command: str
    args: list[str] = []
    env: dict[str, str] | None = None


class HttpMCPConfig(BaseModel):
    """Configuration for HTTP-based MCP servers."""

    url: str
    auth_type: Literal["none", "bearer", "oauth"] = "none"
    bearer_token: str | None = None


# Database Models


class MCPServerConfig(Base):
    """MCP server connection configuration."""

    __tablename__ = "mcp_server_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    server_type: Mapped[MCPServerType] = mapped_column(Enum(MCPServerType))
    config_json: Mapped[str] = mapped_column(Text)  # JSON validated against Pydantic models


class OAuthProvider(Base):
    """Static OAuth provider configuration for traditional integrations."""

    __tablename__ = "oauth_providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    provider_type: Mapped[OAuthProviderType] = mapped_column(Enum(OAuthProviderType))

    # OAuth client credentials
    client_id: Mapped[str] = mapped_column(String(255))
    client_secret: Mapped[str] = mapped_column(String(512))

    # OAuth endpoints
    authorization_url: Mapped[str] = mapped_column(String(1024))
    token_url: Mapped[str] = mapped_column(String(1024))

    # Default scopes to request
    scopes: Mapped[str] = mapped_column(String(1024))  # Space-separated scopes


class OAuthToken(Base):
    """Stored OAuth tokens for both static providers and MCP servers."""

    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_key: Mapped[str] = mapped_column(String(255), unique=True)  # e.g., "oauth-1" or "mcp-1"

    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    token_type: Mapped[str] = mapped_column(String(50), default="Bearer")

    expires_at: Mapped[datetime.datetime | None] = mapped_column()
    scopes: Mapped[str | None] = mapped_column(String(1024))  # Space-separated scopes

    # Full token response JSON (preserves any provider-specific fields)
    raw_token_response: Mapped[str | None] = mapped_column(Text)


class OAuthClientInfo(Base):
    """Dynamic client registration data (primarily for MCP servers using RFC 7591)."""

    __tablename__ = "oauth_client_info"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_key: Mapped[str] = mapped_column(String(255), unique=True)  # e.g., "mcp-1"

    # Full registration response JSON (deserialized to OAuthClientInformationFull by adapter)
    raw_client_info: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))


class PendingOAuthAuthorization(Base):
    """Tracks in-flight OAuth flows."""

    __tablename__ = "pending_oauth_authorizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_key: Mapped[str] = mapped_column(String(255), unique=True)  # e.g., "oauth-1" or "mcp-1"

    # OAuth state parameter (for validation)
    state: Mapped[str | None] = mapped_column(String(255))

    # PKCE code verifier (if applicable)
    code_verifier: Mapped[str | None] = mapped_column(String(255))

    # The callback URI used for this flow
    redirect_uri: Mapped[str | None] = mapped_column(String(1024))

    # Populated by callback endpoint when received
    authorization_code: Mapped[str | None] = mapped_column(Text)

    initiated_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
