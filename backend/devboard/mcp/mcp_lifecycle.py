"""MCP server lifecycle management.

Provides async lifecycle management for MCP client sessions, supporting both
STDIO and HTTP transports with event-based coordination for setup/teardown
from different async tasks.
"""

import asyncio
import tempfile
from typing import IO, Any

import httpx
import logfire
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from devboard.db.models.mcp_server import (
    MCPServerConfig,
    StdioMCPConfig,
)


def _unwrap_exception_group(exc: BaseException) -> Exception:
    """Extract root cause from single-exception ExceptionGroups."""
    while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        exc = exc.exceptions[0]
    if isinstance(exc, Exception):
        return exc
    return RuntimeError(str(exc))


class MCPLifecycleManager:
    """Manages async lifecycle of an MCP client and session.

    Uses events to allow setup and teardown from different async tasks,
    e.g., setup in one tool call task, teardown later by agent context exit.
    """

    def __init__(
        self,
        server_config: MCPServerConfig,
        oauth_provider: OAuthClientProvider | None = None,
        *,
        capture_stderr: bool = False,
    ):
        """Initialize with an MCP server configuration.

        Args:
            server_config: The MCP server configuration.
            oauth_provider: Optional OAuth provider for OAuth-authenticated HTTP servers.
            capture_stderr: If True, capture stderr output from stdio servers
                instead of forwarding to sys.stderr.

        Raises:
            ValueError: If the server config type is unknown.
        """
        self._server_config = server_config
        self._oauth_provider = oauth_provider
        self._stderr_file: IO[str] | None = None
        if capture_stderr:
            self._stderr_file = tempfile.TemporaryFile(mode="w+")
        self._mcp_client_factory = self._create_client_factory()
        self._mcp_session: ClientSession | None = None
        self._teardown_event = asyncio.Event()
        self._session_initialised_event = asyncio.Event()
        self._lifecycle_task: asyncio.Task[None] | None = None
        self._lifecycle_error: Exception | None = None

    @property
    def server_name(self) -> str:
        """Get the server name for logging."""
        return self._server_config.name

    @property
    def captured_stderr(self) -> str | None:
        """Read captured stderr content. Returns None if not capturing."""
        if not self._stderr_file:
            return None
        self._stderr_file.seek(0)
        content = self._stderr_file.read()
        return content or None

    def _create_client_factory(self) -> Any:
        """Create the MCP client factory based on server config type."""
        typed_config = self._server_config.config

        if isinstance(typed_config, StdioMCPConfig):
            kwargs: dict[str, Any] = {}
            if self._stderr_file:
                kwargs["errlog"] = self._stderr_file
            return stdio_client(
                StdioServerParameters(
                    command=typed_config.command,
                    args=typed_config.args or [],
                    env=typed_config.env,
                ),
                **kwargs,
            )

        if typed_config.auth_type == "oauth" and self._oauth_provider:
            http_client = httpx.AsyncClient(auth=self._oauth_provider)
            return streamable_http_client(typed_config.url, http_client=http_client)

        headers: dict[str, str] = {}
        if typed_config.auth_type == "bearer" and typed_config.bearer_token:
            headers["Authorization"] = f"Bearer {typed_config.bearer_token}"

        http_client = httpx.AsyncClient(headers=headers) if headers else None
        return streamable_http_client(typed_config.url, http_client=http_client)

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
        session = self._mcp_session
        if session is None:
            raise RuntimeError("MCP session not active")
        return session

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
        except BaseException as e:
            self._lifecycle_error = _unwrap_exception_group(e)
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
        if (session := self._mcp_session) is not None:
            logfire.debug("MCP server already active", server_name=self.server_name)
            return session

        with logfire.span("MCP server setup", server_name=self.server_name):
            self._teardown_event.clear()
            self._session_initialised_event.clear()
            self._lifecycle_task = asyncio.create_task(self._run_lifecycle())
            await self._session_initialised_event.wait()

            if self._lifecycle_error:
                logfire.error(
                    "MCP server setup failed",
                    server_name=self.server_name,
                    error=str(self._lifecycle_error),
                )
                raise self._lifecycle_error

            if not self.active:
                if self._lifecycle_task:
                    await self._lifecycle_task
                logfire.error("MCP server failed to initialize", server_name=self.server_name)
                raise RuntimeError("MCP session failed to initialize")

            logfire.info("MCP server setup complete", server_name=self.server_name)
            assert self._mcp_session is not None
            return self._mcp_session

    async def teardown(self) -> None:
        """Exit MCP client and session context."""
        if not self._lifecycle_task or self._lifecycle_task.done():
            return

        logfire.info("MCP server teardown started", server_name=self.server_name)
        self._teardown_event.set()
        await self._lifecycle_task
        logfire.info("MCP server teardown complete", server_name=self.server_name)

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
