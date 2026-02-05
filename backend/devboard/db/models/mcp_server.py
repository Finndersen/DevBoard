"""MCP server configuration database models."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .mcp_server import MCPServerConfig


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
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)

    # Verification status fields
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_verified_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_verified_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship to tools
    tools: Mapped[list["MCPTool"]] = relationship(
        "MCPTool",
        back_populates="server",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def config(self) -> StdioMCPConfig | HttpMCPConfig:
        """Return the typed configuration based on server_type."""
        if self.server_type == MCPServerType.STDIO:
            return StdioMCPConfig.model_validate(self.config_json)
        else:
            return HttpMCPConfig.model_validate(self.config_json)


class MCPTool(Base):
    """Cached tool information from an MCP server."""

    __tablename__ = "mcp_tools"
    __table_args__ = (UniqueConstraint("server_id", "name", name="uq_mcp_tool_server_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("mcp_server_configs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationship back to server
    server: Mapped["MCPServerConfig"] = relationship("MCPServerConfig", back_populates="tools")
