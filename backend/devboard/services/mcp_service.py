"""MCP server configuration service.

Provides business logic for managing MCP server configurations including
CRUD operations and connectivity verification.
"""

from datetime import UTC, datetime
from typing import Any

from devboard.api.schemas.mcp import (
    MCPServerDetailResponse,
    MCPToolInfo,
    MCPToolUpdate,
    VerifyResult,
)
from devboard.api.schemas.oauth import MCPServerConfigCreate, MCPServerConfigUpdate
from devboard.db.models import MCPServerConfig, MCPTool
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

    def get_server_detail(self, server_id: int) -> MCPServerConfig | None:
        """Get an MCP server configuration with tools loaded."""
        return self.repository.get_by_id_with_tools(server_id)

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

    def update_tool(self, server_id: int, tool_id: int, data: MCPToolUpdate) -> MCPTool | None:
        """Update a tool's description."""
        tool = self.repository.get_tool_by_id(tool_id)
        if not tool or tool.server_id != server_id:
            return None
        if data.description is not None:
            tool.description = data.description
        return self.repository.update_tool(tool)

    def _sync_tools(self, server: MCPServerConfig, server_tools: list[MCPToolInfo]) -> None:
        """Sync tools from server response to database cache.

        - New tools (name not in cache): Create with description and input_schema from server
        - Existing tools (name already cached): Skip entirely - do not update any fields
        - Stale tools (cached but not returned by server): Delete from cache
        """
        # Get current cached tools
        cached_tools = self.repository.get_tools_by_server_id(server.id)
        cached_tool_names = {tool.name for tool in cached_tools}
        server_tool_names = {tool.name for tool in server_tools}

        # Find stale tools to delete
        stale_tool_ids = [tool.id for tool in cached_tools if tool.name not in server_tool_names]
        if stale_tool_ids:
            self.repository.delete_tools_by_ids(stale_tool_ids)

        # Create new tools (skip existing ones entirely)
        for server_tool in server_tools:
            if server_tool.name not in cached_tool_names:
                new_tool = MCPTool(
                    server_id=server.id,
                    name=server_tool.name,
                    description=server_tool.description,
                    input_schema=server_tool.input_schema,
                )
                self.repository.create_tool(new_tool)

    async def verify(self, server_id: int) -> MCPServerDetailResponse:
        """Verify connectivity to an MCP server, sync tools, and return server detail."""
        config = self.repository.get_by_id(server_id)
        if not config:
            raise ValueError("Server not found")

        now = datetime.now(UTC)

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

                # Sync tools to database
                self._sync_tools(config, tools)

                # Expire config to force fresh load of tools relationship
                self.repository.expire(config)

                # Update verification status on success
                config.last_verified_at = now
                config.last_verified_success = True
                config.last_verified_error = None
                self.repository.update(config)

                # Return server detail with refreshed tools
                return MCPServerDetailResponse.model_validate(self.repository.get_by_id_with_tools(server_id))

        except Exception as e:
            # Update verification status on failure
            config.last_verified_at = now
            config.last_verified_success = False
            config.last_verified_error = str(e)
            self.repository.update(config)

            # Return server detail (with existing cached tools)
            return MCPServerDetailResponse.model_validate(self.repository.get_by_id_with_tools(server_id))

    async def verify_legacy(self, server_id: int) -> VerifyResult:
        """Verify connectivity to an MCP server (legacy response format)."""
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

    async def run_tool(self, server_id: int, tool_id: int, arguments: dict[str, Any] | None) -> str:
        """Execute an MCP tool with provided arguments.

        Returns the tool result as text.
        Raises ValueError if server or tool not found.
        """
        config = self.repository.get_by_id(server_id)
        if not config:
            raise ValueError("Server not found")

        tool = self.repository.get_tool_by_id(tool_id)
        if not tool or tool.server_id != server_id:
            raise ValueError("Tool not found")

        lifecycle = MCPLifecycleManager(config)
        async with lifecycle as session:
            result = await session.call_tool(tool.name, arguments=arguments or {})
            # Extract text content from result
            if result.content:
                text_parts: list[str] = []
                for content in result.content:
                    if hasattr(content, "text"):
                        text_parts.append(content.text)  # type: ignore[union-attr]
                return "\n".join(text_parts)
            return ""
