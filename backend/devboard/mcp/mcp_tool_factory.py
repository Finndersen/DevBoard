"""MCP tool factory for creating pydantic_ai Tool instances from MCP servers.

Provides an interface for agents to initialize MCP servers from tool names
and get pydantic_ai.Tool instances that wrap MCP tool calls.
"""

from typing import Any

from mcp import ClientSession
from pydantic_ai import Tool

from devboard.db.models import MCPServerConfig
from devboard.mcp.exceptions import MCPToolExecutionError
from devboard.mcp.mcp_lifecycle import MCPLifecycleManager


class MCPToolFactory:
    """Context manager that initializes MCP servers and provides pydantic_ai Tools."""

    def __init__(
        self,
        server_configs: list[MCPServerConfig],
        tool_names: list[str] | None = None,
    ):
        """Initialize the factory.

        Arg
            server_configs: MCP server configurations to initialize.
            tool_names: Optional list of tool names to include. If None, includes all tools.
        """
        self._server_configs = server_configs
        self._tool_names = set(tool_names) if tool_names else None
        self._lifecycle_managers: list[MCPLifecycleManager] = []
        self._tools: list[Tool[Any]] = []

    async def __aenter__(self) -> "MCPToolFactory":
        """Set up MCP connections and create tool wrappers."""
        for config in self._server_configs:
            lifecycle = MCPLifecycleManager(config)
            session = await lifecycle.setup()
            self._lifecycle_managers.append(lifecycle)

            result = await session.list_tools()
            for mcp_tool in result.tools:
                if self._tool_names and mcp_tool.name not in self._tool_names:
                    continue

                tool = self._create_tool_wrapper(session, mcp_tool)
                self._tools.append(tool)

        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: Any,
    ) -> None:
        """Tear down MCP connections."""
        for lifecycle in self._lifecycle_managers:
            await lifecycle.teardown()
        self._lifecycle_managers.clear()
        self._tools.clear()

    def get_tools(self) -> list[Tool[Any]]:
        """Get the list of pydantic_ai Tools."""
        return self._tools

    def _create_tool_wrapper(self, session: ClientSession, mcp_tool: Any) -> Tool[Any]:
        """Create a pydantic_ai Tool that wraps an MCP tool call."""
        tool_name = mcp_tool.name
        tool_description = mcp_tool.description or f"MCP tool: {tool_name}"

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

        call_mcp_tool.__name__ = tool_name
        call_mcp_tool.__doc__ = tool_description

        return Tool(
            function=call_mcp_tool,
            name=tool_name,
            description=tool_description,
            takes_ctx=False,
        )
