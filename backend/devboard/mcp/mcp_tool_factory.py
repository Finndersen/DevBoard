"""MCP tool factory for creating pydantic_ai Tool instances from MCP servers.

Provides an interface for agents to initialize MCP servers from tool names
and get pydantic_ai.Tool instances that wrap MCP tool calls.
"""

import os
from dataclasses import dataclass
from typing import Any

import logfire
from mcp import ClientSession
from mcp.types import TextContent
from pydantic_ai import Tool

from devboard.db.models import MCPTool
from devboard.db.models.mcp_server import HttpMCPConfig
from devboard.mcp.exceptions import MCPToolExecutionError
from devboard.mcp.mcp_lifecycle import MCPLifecycleManager
from devboard.mcp.mcp_oauth_adapter import create_oauth_provider
from devboard.services.oauth_service import OAuthService


@dataclass
class MCPServerSetupFailure:
    server_name: str
    server_id: int
    error: str


class MCPToolFactory:
    """Context manager that initializes MCP servers and provides pydantic_ai Tools."""

    def __init__(self, mcp_tools: list[MCPTool], oauth_service: OAuthService | None = None):
        """Initialize the factory.

        Args:
            mcp_tools: List of MCPTool models to enable. Server configs are extracted
                automatically from the tool relationships.
            oauth_service: Optional OAuthService for OAuth-authenticated servers.
        """
        # Filter to only include tools from verified servers
        self._mcp_tools = [tool for tool in mcp_tools if tool.server.last_verified_success]
        self._oauth_service = oauth_service
        self._lifecycle_managers: dict[int, MCPLifecycleManager] = {}
        self._tools: list[Tool[Any]] = []
        self._setup_failures: list[MCPServerSetupFailure] = []
        self._failed_server_ids: set[int] = set()

    async def _create_lifecycle_manager(self, server_config: Any) -> MCPLifecycleManager:
        """Create an MCPLifecycleManager, with OAuth provider if needed."""
        typed_config = server_config.config
        if isinstance(typed_config, HttpMCPConfig) and typed_config.auth_type == "oauth" and self._oauth_service:
            backend_base_url = os.environ.get("DEVBOARD_BACKEND_URL", "http://localhost:8000")
            oauth_provider = await create_oauth_provider(
                server_id=server_config.id,
                server_url=typed_config.url,
                oauth_service=self._oauth_service,
                backend_base_url=backend_base_url,
                client_id=typed_config.client_id,
                client_secret=typed_config.client_secret,
                scopes=typed_config.scopes,
            )
            return MCPLifecycleManager(server_config, oauth_provider=oauth_provider)
        return MCPLifecycleManager(server_config)

    @property
    def setup_failures(self) -> list[MCPServerSetupFailure]:
        return self._setup_failures

    async def __aenter__(self) -> "MCPToolFactory":
        """Set up MCP connections and create tool wrappers."""
        for mcp_tool in self._mcp_tools:
            if mcp_tool.server_id in self._failed_server_ids:
                continue

            if mcp_tool.server_id not in self._lifecycle_managers:
                lifecycle = await self._create_lifecycle_manager(mcp_tool.server)
                try:
                    await lifecycle.setup()
                except Exception as e:
                    logfire.error(
                        "MCP server setup failed: {server_name} (id={server_id}): {error}",
                        server_name=mcp_tool.server.name,
                        server_id=mcp_tool.server_id,
                        error=str(e),
                    )
                    self._setup_failures.append(
                        MCPServerSetupFailure(
                            server_name=mcp_tool.server.name,
                            server_id=mcp_tool.server_id,
                            error=str(e),
                        )
                    )
                    self._failed_server_ids.add(mcp_tool.server_id)
                    continue
                self._lifecycle_managers[mcp_tool.server_id] = lifecycle

            session = self._lifecycle_managers[mcp_tool.server_id].mcp_session
            self._tools.append(self._create_tool_wrapper(session, mcp_tool))

        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: Any,
    ) -> None:
        """Tear down MCP connections."""
        for lifecycle in self._lifecycle_managers.values():
            await lifecycle.teardown()
        self._lifecycle_managers.clear()
        self._tools.clear()

    def get_tools(self) -> list[Tool[Any]]:
        """Get the list of pydantic_ai Tools."""
        return self._tools

    def _create_tool_wrapper(self, session: ClientSession, mcp_tool: MCPTool) -> Tool[Any]:
        """Create a pydantic_ai Tool that wraps an MCP tool call.

        Args:
            session: The MCP client session for making tool calls
            mcp_tool: The MCPTool model containing name, description, and input_schema

        Returns:
            A pydantic_ai Tool configured with the MCP tool's schema
        """
        tool_name = mcp_tool.name

        async def call_mcp_tool(**kwargs: Any) -> str:
            result = await session.call_tool(tool_name, arguments=kwargs)

            text_parts: list[str] = []
            if result.content:
                for content in result.content:
                    if isinstance(content, TextContent):
                        text_parts.append(content.text)

            if result.isError:
                error_message = "\n".join(text_parts) if text_parts else "MCP tool execution failed"
                raise MCPToolExecutionError(error_message)

            return "\n".join(text_parts)

        return Tool.from_schema(
            function=call_mcp_tool,
            name=tool_name,
            description=mcp_tool.description,
            json_schema=mcp_tool.input_schema or {"type": "object", "properties": {}},
        )
