"""MCP server configuration service.

Provides business logic for managing MCP server configurations including
CRUD operations and connectivity verification.
"""

from devboard.api.schemas.mcp import MCPToolInfo, VerifyResult
from devboard.api.schemas.oauth import MCPServerConfigCreate, MCPServerConfigUpdate
from devboard.db.models import MCPServerConfig
from devboard.db.repositories.mcp_server import MCPServerRepository
from devboard.mcp.mcp_lifecycle import MCPLifecycleManager


class MCPService:
    """Service for MCP server configuration management."""

    def __init__(self, mcp_server_repository: MCPServerRepository):
        self.repository = mcp_server_repository

    def get_all(self) -> list[MCPServerConfig]:
        """Get all MCP server configurations."""
        return self.repository.get_all()

    def get_by_id(self, server_id: int) -> MCPServerConfig | None:
        """Get an MCP server configuration by ID."""
        return self.repository.get_by_id(server_id)

    def create(self, data: MCPServerConfigCreate) -> MCPServerConfig:
        """Create a new MCP server configuration."""
        config = MCPServerConfig(
            name=data.name,
            server_type=data.server_type,
            config_json=data.config_json.model_dump(),
        )
        return self.repository.create(config)

    def update(self, server_id: int, data: MCPServerConfigUpdate) -> MCPServerConfig | None:
        """Update an existing MCP server configuration."""
        existing = self.repository.get_by_id(server_id)
        if not existing:
            return None
        if data.name is not None:
            existing.name = data.name
        if data.server_type is not None:
            existing.server_type = data.server_type
        if data.config_json is not None:
            existing.config_json = data.config_json.model_dump()
        return self.repository.update(existing)

    def delete(self, server_id: int) -> bool:
        """Delete an MCP server configuration."""
        return self.repository.delete(server_id)

    async def verify(self, server_id: int) -> VerifyResult:
        """Verify connectivity to an MCP server by connecting and listing tools."""
        config = self.repository.get_by_id(server_id)
        if not config:
            return VerifyResult(success=False, error="Server not found")

        try:
            lifecycle = MCPLifecycleManager(config)
            async with lifecycle as session:
                result = await session.list_tools()
                tools = [
                    MCPToolInfo(
                        name=tool.name,
                        description=tool.description,
                        input_schema=tool.inputSchema,
                    )
                    for tool in result.tools
                ]
                return VerifyResult(success=True, tools=tools)
        except Exception as e:
            return VerifyResult(success=False, error=str(e))
