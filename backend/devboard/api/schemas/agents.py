"""Agent configuration API schemas."""

from pydantic import BaseModel

from devboard.agents.engines.agent_engines import AgentEngine


class MCPToolSummary(BaseModel):
    """Summary of an MCP tool assigned to an agent role."""

    tool_id: int
    tool_name: str
    server_name: str
    description: str | None = None


class AgentRoleToolsResponse(BaseModel):
    """Response containing MCP tools assigned to an agent role."""

    role: str
    tools: list[MCPToolSummary]


class AddMCPToolRequest(BaseModel):
    """Request to add an MCP tool to an agent role."""

    tool_id: int


class UpdateAgentConfigurationRequestFull(BaseModel):
    """Request to update agent configuration including custom instructions.

    When custom_instructions is provided (even as None), it will update the value.
    When custom_instructions is omitted from the request, the existing value is preserved.
    """

    engine: AgentEngine | None
    model_id: str | None
    custom_instructions: str | None = None
