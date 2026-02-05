"""MCP server lifecycle management.

Provides async lifecycle management for MCP client sessions, supporting both
STDIO and HTTP transports with event-based coordination for setup/teardown
from different async tasks.
"""

import asyncio
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from devboard.db.models.mcp_server import (
    HttpMCPConfig,
    MCPServerConfig,
    StdioMCPConfig,
)


class MCPLifecycleManager:
    """Manages async lifecycle of an MCP client and session.

    Uses events to allow setup and teardown from different async tasks,
    e.g., setup in one tool call task, teardown later by agent context exit.
    """

    def __init__(self, mcp_client_factory: Any):
        """Initialize with an MCP client context manager factory.

        Args:
            mcp_client_factory: Return value of stdio_client() or streamable_http_client()
        """
        self._mcp_client_factory = mcp_client_factory
        self._mcp_session: ClientSession | None = None
        self._teardown_event = asyncio.Event()
        self._session_initialised_event = asyncio.Event()
        self._lifecycle_task: asyncio.Task[None] | None = None
        self._lifecycle_error: Exception | None = None

    @property
    def active(self) -> bool:
        """Check if the MCP session is currently active."""
        return self._mcp_session is not None

    @property
    def mcp_session(self) -> ClientSession:
        """Get the active MCP session.

        Raises:
            RuntimeError: If the session is not active.
        """
        if not self.active:
            raise RuntimeError("MCP session not active")
        return self._mcp_session  # type: ignore[return-value]

    async def _run_lifecycle(self) -> None:
        """Run the lifecycle - enters client context, initializes session, waits for teardown."""
        self._session_initialised_event.clear()
        self._lifecycle_error = None

        try:
            async with self._mcp_client_factory as streams:
                read_stream, write_stream = streams[0], streams[1]
                async with ClientSession(read_stream, write_stream) as session:
                    self._mcp_session = session
                    await session.initialize()
                    self._session_initialised_event.set()
                    await self._teardown_event.wait()
        except Exception as e:
            self._lifecycle_error = e
            self._session_initialised_event.set()
        finally:
            self._mcp_session = None

    async def setup(self) -> ClientSession:
        """Begin MCP client and session context.

        Returns:
            The initialized ClientSession.

        Raises:
            Exception: If the session fails to initialize.
        """
        if self.active:
            return self._mcp_session  # type: ignore[return-value]

        self._teardown_event.clear()
        self._session_initialised_event.clear()
        self._lifecycle_task = asyncio.create_task(self._run_lifecycle())
        await self._session_initialised_event.wait()

        if self._lifecycle_error:
            raise self._lifecycle_error

        if not self.active:
            if self._lifecycle_task:
                await self._lifecycle_task
            raise RuntimeError("MCP session failed to initialize")

        return self._mcp_session  # type: ignore[return-value]

    async def teardown(self) -> None:
        """Exit MCP client and session context."""
        if not self._lifecycle_task or self._lifecycle_task.done():
            return
        self._teardown_event.set()
        await self._lifecycle_task

    async def __aenter__(self) -> ClientSession:
        """Async context manager entry."""
        return await self.setup()

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: Any,
    ) -> None:
        """Async context manager exit."""
        await self.teardown()


def create_mcp_lifecycle_manager(server_config: MCPServerConfig) -> MCPLifecycleManager:
    """Create an MCPLifecycleManager from a server configuration.

    Routes to the appropriate transport (STDIO or HTTP) based on config.

    Args:
        server_config: The MCP server configuration.

    Returns:
        An MCPLifecycleManager configured for the server.

    Raises:
        ValueError: If the server type is unknown.
    """
    typed_config = server_config.config

    if isinstance(typed_config, StdioMCPConfig):
        mcp_client = stdio_client(
            StdioServerParameters(
                command=typed_config.command,
                args=typed_config.args or [],
                env=typed_config.env,
            )
        )
        return MCPLifecycleManager(mcp_client)

    elif isinstance(typed_config, HttpMCPConfig):
        headers: dict[str, str] = {}
        if typed_config.auth_type == "bearer" and typed_config.bearer_token:
            headers["Authorization"] = f"Bearer {typed_config.bearer_token}"

        http_client = httpx.AsyncClient(headers=headers) if headers else None
        mcp_client = streamable_http_client(typed_config.url, http_client=http_client)
        return MCPLifecycleManager(mcp_client)

    else:
        raise ValueError(f"Unknown config type: {type(typed_config)}")
