"""Schemas for agent configuration inspector endpoint."""

from typing import Any, Literal

from pydantic import BaseModel


class ToolInfo(BaseModel):
    """Information about a tool available to an agent."""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    source: Literal["role", "mcp", "builtin"]
    server_name: str | None = None  # Only for MCP tools


class AgentConfigResponse(BaseModel):
    """Full assembled configuration for an agent conversation."""

    agent_role: str
    behaviour_guidelines: str
    context_content: str
    custom_instructions: str | None
    role_tools: list[ToolInfo]
    mcp_tools: list[ToolInfo]
    builtin_tools: list[ToolInfo]
