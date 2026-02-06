"""MCP server configuration API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.entities import get_verified_mcp_server_config
from devboard.api.dependencies.services import get_mcp_service
from devboard.api.schemas import (
    DeleteResponse,
    MCPServerConfigCreate,
    MCPServerConfigResponse,
    MCPServerConfigUpdate,
    MCPServerDetailResponse,
    MCPToolResponse,
    MCPToolRunRequest,
    MCPToolRunResponse,
    MCPToolUpdate,
)
from devboard.db.models import MCPServerConfig
from devboard.mcp.exceptions import MCPToolExecutionError
from devboard.services.mcp_service import MCPService

router = APIRouter()


@router.get("/", response_model=list[MCPServerConfigResponse])
async def list_mcp_servers(
    mcp_service: MCPService = Depends(get_mcp_service),
) -> list[MCPServerConfig]:
    """List all MCP server configurations."""
    return mcp_service.get_all()


@router.get("/{server_id}", response_model=MCPServerDetailResponse)
async def get_mcp_server(
    server_id: int,
    mcp_server: MCPServerConfig = Depends(get_verified_mcp_server_config),
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPServerDetailResponse:
    """Get a specific MCP server configuration with tools and verification status."""
    server = mcp_service.get_server_detail(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return MCPServerDetailResponse.model_validate(server)


@router.post("/", response_model=MCPServerConfigResponse)
async def create_mcp_server(
    data: MCPServerConfigCreate,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPServerConfig:
    """Create a new MCP server configuration."""
    return mcp_service.create(data)


@router.put("/{server_id}", response_model=MCPServerConfigResponse)
async def update_mcp_server(
    server_id: int,
    data: MCPServerConfigUpdate,
    mcp_server: MCPServerConfig = Depends(get_verified_mcp_server_config),
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPServerConfig:
    """Update an existing MCP server configuration."""
    updated = mcp_service.update(server_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return updated


@router.delete("/{server_id}", response_model=DeleteResponse)
async def delete_mcp_server(
    server_id: int,
    mcp_server: MCPServerConfig = Depends(get_verified_mcp_server_config),
    mcp_service: MCPService = Depends(get_mcp_service),
) -> DeleteResponse:
    """Delete an MCP server configuration."""
    deleted = mcp_service.delete(server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return DeleteResponse(message="MCP server deleted successfully", success=True)


@router.post("/{server_id}/verify", response_model=MCPServerDetailResponse)
async def verify_mcp_server(
    server_id: int,
    mcp_server: MCPServerConfig = Depends(get_verified_mcp_server_config),
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPServerDetailResponse:
    """Verify connectivity to an MCP server, sync tools, and return server detail."""
    return await mcp_service.verify(server_id)


@router.put("/{server_id}/tools/{tool_id}", response_model=MCPToolResponse)
async def update_mcp_tool(
    server_id: int,
    tool_id: int,
    data: MCPToolUpdate,
    mcp_server: MCPServerConfig = Depends(get_verified_mcp_server_config),
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPToolResponse:
    """Update an MCP tool's description."""
    tool = mcp_service.update_tool(server_id, tool_id, data)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return MCPToolResponse.model_validate(tool)


@router.post("/{server_id}/tools/{tool_id}/run", response_model=MCPToolRunResponse)
async def run_mcp_tool(
    server_id: int,
    tool_id: int,
    data: MCPToolRunRequest,
    mcp_server: MCPServerConfig = Depends(get_verified_mcp_server_config),
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPToolRunResponse:
    """Execute an MCP tool with provided arguments."""
    try:
        result = await mcp_service.run_tool(server_id, tool_id, data.arguments)
        return MCPToolRunResponse(success=True, result=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except MCPToolExecutionError as e:
        return MCPToolRunResponse(success=False, error=str(e))
    except Exception as e:
        return MCPToolRunResponse(success=False, error=str(e))
