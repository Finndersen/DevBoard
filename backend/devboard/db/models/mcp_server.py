"""MCP server configuration database models."""

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
