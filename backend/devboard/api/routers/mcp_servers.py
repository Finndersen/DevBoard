"""MCP server configuration API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.entities import get_verified_mcp_server_config
from devboard.api.dependencies.services import get_mcp_service
from devboard.api.schemas import (
    DeleteResponse,
    MCPServerConfigCreate,
    MCPServerConfigResponse,
    MCPServerConfigUpdate,
    VerifyResult,
)
from devboard.db.models import MCPServerConfig
from devboard.services.mcp_service import MCPService

router = APIRouter()


@router.get("/", response_model=list[MCPServerConfigResponse])
async def list_mcp_servers(
    mcp_service: MCPService = Depends(get_mcp_service),
) -> list[MCPServerConfig]:
    """List all MCP server configurations."""
    return mcp_service.get_all()


@router.get("/{server_id}", response_model=MCPServerConfigResponse)
async def get_mcp_server(
    server_id: int,
    mcp_server: MCPServerConfig = Depends(get_verified_mcp_server_config),
) -> MCPServerConfig:
    """Get a specific MCP server configuration."""
    return mcp_server


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


@router.post("/{server_id}/verify", response_model=VerifyResult)
async def verify_mcp_server(
    server_id: int,
    mcp_server: MCPServerConfig = Depends(get_verified_mcp_server_config),
    mcp_service: MCPService = Depends(get_mcp_service),
) -> VerifyResult:
    """Verify connectivity to an MCP server and list available tools."""
    return await mcp_service.verify(server_id)
