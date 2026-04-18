"""Agents API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.agent_config_assembly import assemble_agent_config
from devboard.agents.agent_config_service import (
    AgentConfigService,
    AgentConfiguration,
    AvailableModelsByEngine,
)
from devboard.agents.config_types import AgentEngineModelInput
from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.repositories import get_mcp_server_repository
from devboard.api.dependencies.services import ExecutionServices, get_agent_config_service, get_execution_services
from devboard.api.schemas import (
    AddMCPToolRequest,
    AgentRoleToolsResponse,
    MCPToolSummary,
    UpdateAgentConfigurationRequestFull,
)
from devboard.api.schemas.agent_config import AgentConfigResponse
from devboard.db.models import Conversation
from devboard.db.repositories import MCPServerRepository

router = APIRouter()


def _parse_agent_role(agent_role: str) -> AgentRoleType:
    """Parse and validate agent role string."""
    try:
        return AgentRoleType(agent_role)
    except ValueError:
        valid_roles = [r.value for r in AgentRoleType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent role: {agent_role}. Must be one of: {', '.join(valid_roles)}",
        ) from None


@router.get("/{agent_role}/configuration", response_model=AgentConfiguration)
async def get_agent_configuration(
    agent_role: str,
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AgentConfiguration:
    """Get configuration for an agent role.

    Returns the effective engine and model configuration, along with
    available engines for the role and custom instructions.
    """
    role = _parse_agent_role(agent_role)
    return service.get_agent_configuration(role)


@router.put("/{agent_role}/configuration", response_model=AgentConfiguration)
async def update_agent_configuration(
    agent_role: str,
    request: UpdateAgentConfigurationRequestFull,
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AgentConfiguration:
    """Update configuration for an agent role.

    Updates engine, model, and custom instructions for the role. Validates that:
    - Engine is allowed for the role
    - Model is available for the engine (provider configured)
    """
    role = _parse_agent_role(agent_role)

    try:
        config = AgentEngineModelInput(
            engine=AgentEngine(request.engine),
            model_id=request.model_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    try:
        return service.update_agent_configuration(role, config, request.custom_instructions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/available-models", response_model=AvailableModelsByEngine)
async def get_available_models_by_engine(
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AvailableModelsByEngine:
    """Get all available models grouped by engine.

    Returns models from all configured providers, organized by which
    engine supports them.
    """
    return service.get_available_models_by_engine()


@router.get("/{agent_role}/tools", response_model=AgentRoleToolsResponse)
async def get_agent_role_tools(
    agent_role: str,
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AgentRoleToolsResponse:
    """Get MCP tools assigned to an agent role."""
    role = _parse_agent_role(agent_role)
    mcp_tools = service.get_enabled_mcp_tools(role)

    tools = [
        MCPToolSummary(
            tool_id=tool.id,
            tool_name=tool.name,
            server_name=tool.server.name,
            description=tool.description,
        )
        for tool in mcp_tools
    ]

    return AgentRoleToolsResponse(role=role.value, tools=tools)


@router.post("/{agent_role}/tools", status_code=201)
async def add_agent_role_tool(
    agent_role: str,
    request: AddMCPToolRequest,
    service: AgentConfigService = Depends(get_agent_config_service),
) -> dict[str, str]:
    """Add an MCP tool to an agent role."""
    role = _parse_agent_role(agent_role)

    try:
        service.add_mcp_tool(role, request.tool_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return {"status": "ok"}


@router.delete("/{agent_role}/tools/{tool_id}", status_code=200)
async def remove_agent_role_tool(
    agent_role: str,
    tool_id: int,
    service: AgentConfigService = Depends(get_agent_config_service),
) -> dict[str, str]:
    """Remove an MCP tool from an agent role."""
    role = _parse_agent_role(agent_role)

    try:
        service.remove_mcp_tool(role, tool_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return {"status": "ok"}


@router.get("/available-mcp-tools", response_model=list[MCPToolSummary])
async def get_available_mcp_tools(
    mcp_server_repo: MCPServerRepository = Depends(get_mcp_server_repository),
) -> list[MCPToolSummary]:
    """Get all available MCP tools from verified servers.

    Returns tools only from MCP servers that have been successfully verified.
    These tools can be assigned to agent roles.
    """
    tools = mcp_server_repo.get_all_tools_from_verified_servers()
    return [
        MCPToolSummary(
            tool_id=tool.id,
            tool_name=tool.name,
            server_name=tool.server.name,
            description=tool.description,
        )
        for tool in tools
    ]


@router.get("/conversations/{conversation_id}/config", response_model=AgentConfigResponse)
async def get_conversation_agent_config(
    conversation: Conversation = Depends(get_verified_conversation),
    exec_services: ExecutionServices = Depends(get_execution_services),
) -> AgentConfigResponse:
    """Get the full assembled agent configuration for a conversation."""
    return await assemble_agent_config(
        conversation=conversation,
        document_repo=exec_services.document_repo,
        agent_config_service=exec_services.agent_config_service,
        integration_service=exec_services.integration_service,
        task_service=exec_services.task_service,
        conversation_repo=exec_services.conversation_repo,
    )
