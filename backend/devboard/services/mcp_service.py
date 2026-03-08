"""MCP server configuration service.

Provides business logic for managing MCP server configurations including
CRUD operations and connectivity verification.
"""

import os
from typing import Any

from devboard.api.schemas.mcp import (
    MCPServerDetailResponse,
    MCPToolInfo,
    MCPToolUpdate,
    OAuthStatusResponse,
    VerifyResult,
)
from devboard.api.schemas.oauth import MCPServerConfigCreate, MCPServerConfigUpdate
from devboard.db.models import MCPServerConfig, MCPTool
from devboard.db.models.mcp_server import HttpMCPConfig
from devboard.db.repositories.mcp_server import MCPServerRepository
from devboard.mcp.exceptions import MCPToolExecutionError
from devboard.mcp.mcp_lifecycle import MCPLifecycleManager
from devboard.mcp.mcp_oauth_adapter import create_oauth_provider
from devboard.services.oauth_service import OAuthService


class MCPService:
    """Service for MCP server configuration management."""

    def __init__(
        self,
        mcp_server_repository: MCPServerRepository,
        oauth_service: OAuthService | None = None,
    ):
        self.repository = mcp_server_repository
        self._oauth_service = oauth_service

    def get_all(self) -> list[MCPServerConfig]:
        """Get all MCP server configurations."""
        return self.repository.get_all()

    def get_by_id(self, server_id: int) -> MCPServerConfig | None:
        """Get an MCP server configuration by ID."""
        return self.repository.get_by_id(server_id)

    def get_server_detail(self, server_id: int) -> MCPServerDetailResponse | None:
        """Get an MCP server detail response with tools and OAuth status."""
        server = self.repository.get_by_id_with_tools(server_id)
        if not server:
            return None
        response = MCPServerDetailResponse.model_validate(server)
        response.oauth_status = self._get_oauth_status(server)
        return response

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

    def _get_oauth_status(self, server: MCPServerConfig) -> OAuthStatusResponse | None:
        """Get OAuth status for a server if it uses OAuth auth."""
        typed_config = server.config
        if not isinstance(typed_config, HttpMCPConfig) or typed_config.auth_type != "oauth":
            return None
        if not self._oauth_service:
            return None

        provider_key = OAuthService.generate_mcp_provider_key(server.id)
        has_tokens = self._oauth_service.get_tokens(provider_key) is not None
        token_expired = self._oauth_service.is_token_expired(provider_key) if has_tokens else False
        has_client_info = self._oauth_service.get_client_info(provider_key) is not None

        return OAuthStatusResponse(
            has_tokens=has_tokens,
            token_expired=token_expired,
            has_client_info=has_client_info,
        )

    def _build_detail_response(self, server_id: int) -> MCPServerDetailResponse:
        """Build an MCPServerDetailResponse with OAuth status if applicable."""
        server = self.repository.get_by_id_with_tools(server_id)
        response = MCPServerDetailResponse.model_validate(server)
        if server:
            response.oauth_status = self._get_oauth_status(server)
        return response

    async def _create_lifecycle_manager(
        self, config: MCPServerConfig, *, capture_stderr: bool = False
    ) -> MCPLifecycleManager:
        """Create an MCPLifecycleManager, with OAuth provider if needed."""
        typed_config = config.config
        if isinstance(typed_config, HttpMCPConfig) and typed_config.auth_type == "oauth" and self._oauth_service:
            backend_base_url = os.environ.get("DEVBOARD_BACKEND_URL", "http://localhost:8000")
            oauth_provider = await create_oauth_provider(
                server_id=config.id,
                server_url=typed_config.url,
                oauth_service=self._oauth_service,
                backend_base_url=backend_base_url,
                client_id=typed_config.client_id,
                client_secret=typed_config.client_secret,
                scopes=typed_config.scopes,
            )
            return MCPLifecycleManager(config, oauth_provider=oauth_provider, capture_stderr=capture_stderr)
        return MCPLifecycleManager(config, capture_stderr=capture_stderr)

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

        lifecycle: MCPLifecycleManager | None = None
        try:
            lifecycle = await self._create_lifecycle_manager(config, capture_stderr=True)
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

                if not tools:
                    error = "Server returned no tools"
                    stderr = lifecycle.captured_stderr
                    if stderr:
                        error += f"\n\n[stderr]\n{stderr.strip()}"
                    self.repository.update_verification_status(config, success=False, error=error)
                    return MCPServerDetailResponse.model_validate(self.repository.get_by_id_with_tools(server_id))

                # Sync tools to database
                self._sync_tools(config, tools)

                # Expire config to force fresh load of tools relationship
                self.repository.expire(config)

                self.repository.update_verification_status(config, success=True, error=None)
                return self._build_detail_response(server_id)

        except Exception as e:
            error = str(e)
            stderr = lifecycle.captured_stderr if lifecycle else None
            if stderr:
                error += f"\n\n[stderr]\n{stderr.strip()}"
            self.repository.update_verification_status(config, success=False, error=error)
            return MCPServerDetailResponse.model_validate(self.repository.get_by_id_with_tools(server_id))

    async def verify_legacy(self, server_id: int) -> VerifyResult:
        """Verify connectivity to an MCP server (legacy response format)."""
        config = self.repository.get_by_id(server_id)
        if not config:
            return VerifyResult(success=False, error="Server not found")

        try:
            lifecycle = await self._create_lifecycle_manager(config)
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

        lifecycle = await self._create_lifecycle_manager(config)
        async with lifecycle as session:
            result = await session.call_tool(tool.name, arguments=arguments or {})

            # Extract text content from result
            text_parts: list[str] = []
            if result.content:
                for content in result.content:
                    if hasattr(content, "text"):
                        text_parts.append(content.text)  # type: ignore[union-attr]

            # Check for error response from MCP server
            if result.isError:
                error_message = "\n".join(text_parts) if text_parts else "MCP tool execution failed"
                raise MCPToolExecutionError(error_message)

            return "\n".join(text_parts)
