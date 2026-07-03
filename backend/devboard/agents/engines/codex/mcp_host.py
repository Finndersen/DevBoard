from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from typing import Any

import logfire
import uvicorn
from mcp import types as mcp_types
from mcp.server.lowlevel import Server as LowLevelMCPServer
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from pydantic_ai import Tool
from starlette.applications import Starlette
from starlette.routing import Mount


class _SuppressMCPTeardownNoise(logging.Filter):
    """Suppress benign connection-teardown ERROR logs from the MCP library.

    Two patterns to handle:
    - streamable_http uses logger.exception() so exc_info is set; the exception
      type is starlette.exceptions.ClientDisconnect.
    - lowlevel server uses logger.error(f"...{exc}") with an f-string, so exc_info
      is NOT set and str(ClientDisconnect()) is empty — match on the message prefix.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "ClientDisconnect" in msg:
            return False
        # lowlevel server: "Received exception from stream: " (exc is an empty-str repr)
        if msg.startswith("Received exception from stream:"):
            return False
        # streamable_http: "Error handling POST request" with exc_info=ClientDisconnect
        if record.exc_info:
            exc_type = record.exc_info[0]
            if exc_type is not None and "ClientDisconnect" in exc_type.__name__:
                return False
        return True


_mcp_filter = _SuppressMCPTeardownNoise()
logging.getLogger("mcp.server.streamable_http").addFilter(_mcp_filter)
logging.getLogger("mcp.server.lowlevel.server").addFilter(_mcp_filter)


class HarnessMCPHost:
    """
    Hosts multiple MCP servers as one HTTP server on an ephemeral port.
    One instance per Codex agent run. NOT a singleton.

    Lifecycle:
        host = HarnessMCPHost()
        host.add_server("foo", server_a)
        host.add_server("bar", server_b)
        port = await host.start()
        # ... use host.url_for("foo") in codex config_overrides ...
        await host.stop()
    """

    def __init__(self) -> None:
        self._servers: dict[str, LowLevelMCPServer] = {}
        self._session_managers: dict[str, StreamableHTTPSessionManager] = {}
        self._starlette_app: Starlette | None = None
        self._uvicorn_server: uvicorn.Server | None = None
        self._uvicorn_task: asyncio.Task[None] | None = None
        self._bound_socket: socket.socket | None = None
        self._port: int | None = None
        self._started: bool = False

    def add_server(self, name: str, server: LowLevelMCPServer) -> None:
        """Register an mcp.server.lowlevel.Server to be served at /mcp/<name>.

        Must be called before start(). The Server should already have its
        tools/list and tools/call handlers registered.
        """
        if self._started:
            raise RuntimeError("Cannot add_server after start() has been called.")
        self._servers[name] = server

    async def start(self) -> int:
        """Bind an ephemeral port, build the Starlette app, and run uvicorn.

        Raises if called more than once or if no servers were added.
        Returns the assigned port.
        """
        if self._started:
            raise RuntimeError("HarnessMCPHost.start() has already been called.")
        if not self._servers:
            raise RuntimeError("No MCP servers registered. Call add_server() before start().")

        self._started = True

        # Pre-bind socket so port is known before uvicorn starts
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        self._port = sock.getsockname()[1]
        self._bound_socket = sock

        try:
            # Build one session manager per registered server
            for name, server in self._servers.items():
                self._session_managers[name] = StreamableHTTPSessionManager(
                    app=server,
                    stateless=True,
                    json_response=True,
                )

            # Capture for closure
            session_managers = self._session_managers

            @contextlib.asynccontextmanager
            async def lifespan(app: Starlette):  # type: ignore[type-arg]
                async with contextlib.AsyncExitStack() as stack:
                    for sm in session_managers.values():
                        await stack.enter_async_context(sm.run())
                    yield

            routes = [Mount(f"/mcp/{name}", app=sm.handle_request) for name, sm in self._session_managers.items()]
            self._starlette_app = Starlette(routes=routes, lifespan=lifespan)

            config = uvicorn.Config(
                app=self._starlette_app,
                fd=sock.fileno(),
                log_level="warning",
                lifespan="on",
            )
            self._uvicorn_server = uvicorn.Server(config)
            self._uvicorn_task = asyncio.create_task(self._uvicorn_server.serve())

            for _ in range(100):
                if self._uvicorn_server.started:
                    logfire.debug("HarnessMCPHost started on port {port}", port=self._port)
                    return self._port
                await asyncio.sleep(0.05)

            raise RuntimeError("uvicorn server failed to start within 5s")
        except Exception:
            self._bound_socket.close()
            self._bound_socket = None
            raise

    async def stop(self) -> None:
        """Shut down uvicorn. Idempotent."""
        if self._uvicorn_server is None:
            return
        self._uvicorn_server.should_exit = True
        assert self._uvicorn_task is not None
        try:
            await asyncio.wait_for(self._uvicorn_task, timeout=5.0)
        except TimeoutError:
            self._uvicorn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._uvicorn_task
        self._uvicorn_server = None
        self._uvicorn_task = None
        if self._bound_socket is not None:
            self._bound_socket.close()
            self._bound_socket = None

    @property
    def port(self) -> int | None:
        return self._port

    def url_for(self, name: str) -> str:
        """Returns http://127.0.0.1:<port>/mcp/<name>/. Requires start() to have been called."""
        if self._port is None:
            raise RuntimeError("HarnessMCPHost.start() has not been called")
        if name not in self._servers:
            raise KeyError(name)
        # Starlette Mount serves at /mcp/<name>/ with trailing slash; include it to avoid 307 redirect
        return f"http://127.0.0.1:{self._port}/mcp/{name}/"

    def mcp_config_entries(self) -> dict[str, dict[str, Any]]:
        """Returns the dict to merge into Codex config_overrides mcpServers map.

        Example: {"foo": {"type": "http", "url": "http://127.0.0.1:54321/mcp/foo/", "alwaysLoad": True}}
        """
        return {
            name: {
                "type": "http",
                "url": self.url_for(name),
                "alwaysLoad": True,
            }
            for name in self._servers
        }


def create_mcp_server_from_tools(name: str, tools: list[Tool]) -> LowLevelMCPServer:  # type: ignore[type-arg]
    """Create an mcp.server.lowlevel.Server from a list of PydanticAI Tool instances."""
    server = LowLevelMCPServer(name)
    tool_map: dict[str, Tool] = {tool.name: tool for tool in tools}  # type: ignore[type-arg]

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=tool.name,
                description=tool.description or "",
                inputSchema=tool.function_schema.json_schema,
            )
            for tool in tools
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(tool_name: str, arguments: dict[str, Any]) -> list[mcp_types.TextContent]:
        if tool_name not in tool_map:
            raise ValueError(f"Tool '{tool_name}' not found")

        tool = tool_map[tool_name]

        with logfire.span(
            f"Calling tool: {tool_name}()",
            tool_name=tool_name,
            args=arguments,
        ):
            try:
                validated_args = tool.function_schema.validator.validate_python(arguments)
                result = await tool.function_schema.call(validated_args, ctx=None)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
            except Exception as e:
                logfire.exception(
                    f"Tool execution failed: {tool_name}",
                    tool_name=tool_name,
                )
                # Raise so the MCP framework wraps this in CallToolResult(isError=True)
                raise RuntimeError(f"Tool execution error: {e}") from e

            if isinstance(result, dict) and "content" in result:
                return [
                    mcp_types.TextContent(type="text", text=item["text"])
                    for item in result["content"]
                    if item.get("type") == "text"
                ]
            return [mcp_types.TextContent(type="text", text=str(result))]  # type: ignore[return-value]

    return server
