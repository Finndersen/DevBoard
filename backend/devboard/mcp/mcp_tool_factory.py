"""MCP tool factory for creating pydantic_ai Tool instances from MCP servers.

Provides an interface for agents to initialize MCP servers from tool names
and get pydantic_ai.Tool instances that wrap MCP tool calls.
"""

from typing import Any

from mcp import ClientSession
from pydantic_ai import Tool

from devboard.db.models import MCPTool
from devboard.mcp.exceptions import MCPToolExecutionError
from devboard.mcp.mcp_lifecycle import MCPLifecycleManager


class MCPToolFactory:
    """Context manager that initializes MCP servers and provides pydantic_ai Tools."""

    def __init__(self, mcp_tools: list[MCPTool]):
        """Initialize the factory.

        Args:
            mcp_tools: List of MCPTool models to enable. Server configs are extracted
                automatically from the tool relationships.
        """
        # Filter to only include tools from verified servers
        self._mcp_tools = [tool for tool in mcp_tools if tool.server.last_verified_success]
        self._lifecycle_managers: dict[int, MCPLifecycleManager] = {}
        self._tools: list[Tool[Any]] = []

    async def __aenter__(self) -> "MCPToolFactory":
        """Set up MCP connections and create tool wrappers."""
        for mcp_tool in self._mcp_tools:
            if mcp_tool.server_id not in self._lifecycle_managers:
                lifecycle = MCPLifecycleManager(mcp_tool.server)
                await lifecycle.setup()
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
                    if hasattr(content, "text"):
                        text_parts.append(content.text)  # type: ignore[union-attr]

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
