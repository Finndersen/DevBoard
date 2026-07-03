"""Tests for HarnessMCPHost and create_mcp_server_from_tools."""

from __future__ import annotations

import socket

import pytest
from mcp import types as mcp_types
from mcp.server.lowlevel import Server as LowLevelMCPServer
from pydantic_ai import Tool

from devboard.agents.engines.codex.mcp_host import HarnessMCPHost, create_mcp_server_from_tools


def _can_bind_socket() -> bool:
    """Return False when the OS sandbox blocks socket binding (e.g. Claude Code agent env)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.close()
        return True
    except PermissionError:
        return False


_SOCKET_AVAILABLE = _can_bind_socket()
_skip_if_no_socket = pytest.mark.skipif(
    not _SOCKET_AVAILABLE,
    reason="socket binding not available in this environment (sandboxed)",
)


def _make_trivial_mcp_server() -> LowLevelMCPServer:
    """Create a minimal LowLevelMCPServer with a single no-op tool."""
    server = LowLevelMCPServer("trivial")

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[mcp_types.Tool]:
        return [mcp_types.Tool(name="noop", description="no-op", inputSchema={"type": "object", "properties": {}})]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
        return [mcp_types.TextContent(type="text", text="ok")]

    return server


# ---------------------------------------------------------------------------
# HarnessMCPHost tests
# ---------------------------------------------------------------------------


class TestHarnessMCPHost:
    @_skip_if_no_socket
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        host = HarnessMCPHost()
        host.add_server("trivial", _make_trivial_mcp_server())
        port = await host.start()
        assert isinstance(port, int)
        assert port > 0
        assert host.port == port
        url = host.url_for("trivial")
        assert url == f"http://127.0.0.1:{port}/mcp/trivial/"
        await host.stop()

    @_skip_if_no_socket
    @pytest.mark.asyncio
    async def test_add_server_after_start_raises(self):
        host = HarnessMCPHost()
        host.add_server("trivial", _make_trivial_mcp_server())
        await host.start()
        try:
            with pytest.raises(RuntimeError, match="Cannot add_server after start"):
                host.add_server("other", _make_trivial_mcp_server())
        finally:
            await host.stop()

    @pytest.mark.asyncio
    async def test_start_without_servers_raises(self):
        host = HarnessMCPHost()
        with pytest.raises(RuntimeError, match="No MCP servers registered"):
            await host.start()

    @_skip_if_no_socket
    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        host = HarnessMCPHost()
        host.add_server("trivial", _make_trivial_mcp_server())
        await host.start()
        await host.stop()
        # Second stop should not raise
        await host.stop()

    @pytest.mark.asyncio
    async def test_stop_before_start_is_safe(self):
        host = HarnessMCPHost()
        await host.stop()  # Should not raise

    @_skip_if_no_socket
    @pytest.mark.asyncio
    async def test_mcp_config_entries(self):
        host = HarnessMCPHost()
        host.add_server("tools", _make_trivial_mcp_server())
        port = await host.start()
        try:
            entries = host.mcp_config_entries()
            assert entries == {
                "tools": {
                    "type": "http",
                    "url": f"http://127.0.0.1:{port}/mcp/tools/",
                    "alwaysLoad": True,
                }
            }
        finally:
            await host.stop()

    def test_url_for_before_start_raises(self):
        host = HarnessMCPHost()
        host.add_server("trivial", _make_trivial_mcp_server())
        with pytest.raises(RuntimeError, match="start\\(\\) has not been called"):
            host.url_for("trivial")

    def test_url_for_unknown_server_raises(self):
        host = HarnessMCPHost()
        host.add_server("trivial", _make_trivial_mcp_server())
        # port is None so RuntimeError is raised first, so test with a workaround:
        # Manually set port to simulate post-start state
        host._port = 12345  # type: ignore[attr-defined]
        with pytest.raises(KeyError):
            host.url_for("unknown")


# ---------------------------------------------------------------------------
# create_mcp_server_from_tools tests
# ---------------------------------------------------------------------------


async def _add(a: int, b: int) -> str:
    """Add two numbers."""
    return str(a + b)


async def _failing_tool(x: str) -> str:
    """A tool that always raises."""
    raise ValueError(f"intentional failure: {x}")


class TestCreateMCPServerFromTools:
    def _make_add_tool(self) -> Tool:  # type: ignore[type-arg]
        return Tool(_add)

    def _make_failing_tool(self) -> Tool:  # type: ignore[type-arg]
        return Tool(_failing_tool)

    @pytest.mark.asyncio
    async def test_list_tools_returns_correct_schema(self):
        server = create_mcp_server_from_tools("test", [self._make_add_tool()])
        handler = server.request_handlers[mcp_types.ListToolsRequest]
        result = await handler(None)

        assert len(result.root.tools) == 1
        tool = result.root.tools[0]
        assert tool.name == "_add"
        assert "a" in tool.inputSchema.get("properties", {})
        assert "b" in tool.inputSchema.get("properties", {})

    @pytest.mark.asyncio
    async def test_call_tool_with_valid_args(self):
        server = create_mcp_server_from_tools("test", [self._make_add_tool()])
        req = mcp_types.CallToolRequest(
            method="tools/call",
            params=mcp_types.CallToolRequestParams(name="_add", arguments={"a": 3, "b": 4}),
        )
        handler = server.request_handlers[mcp_types.CallToolRequest]
        result = await handler(req)

        call_result = result.root
        assert isinstance(call_result, mcp_types.CallToolResult)
        assert call_result.isError is False
        assert len(call_result.content) == 1
        assert call_result.content[0].text == "7"

    @pytest.mark.asyncio
    async def test_call_tool_with_invalid_args_returns_error(self):
        server = create_mcp_server_from_tools("test", [self._make_add_tool()])
        # Pass strings instead of ints — pydantic may coerce or fail
        req = mcp_types.CallToolRequest(
            method="tools/call",
            params=mcp_types.CallToolRequestParams(name="_add", arguments={"a": "not_a_number", "b": 4}),
        )
        handler = server.request_handlers[mcp_types.CallToolRequest]
        result = await handler(req)

        call_result = result.root
        # pydantic validation failure → RuntimeError raised → isError=True
        assert isinstance(call_result, mcp_types.CallToolResult)
        assert call_result.isError is True

    @pytest.mark.asyncio
    async def test_call_unknown_tool_returns_error(self):
        server = create_mcp_server_from_tools("test", [self._make_add_tool()])
        req = mcp_types.CallToolRequest(
            method="tools/call",
            params=mcp_types.CallToolRequestParams(name="unknown_tool", arguments={}),
        )
        handler = server.request_handlers[mcp_types.CallToolRequest]
        result = await handler(req)

        call_result = result.root
        assert isinstance(call_result, mcp_types.CallToolResult)
        assert call_result.isError is True
        assert "unknown_tool" in call_result.content[0].text

    @pytest.mark.asyncio
    async def test_call_tool_that_raises_returns_error(self):
        server = create_mcp_server_from_tools("test", [self._make_failing_tool()])
        req = mcp_types.CallToolRequest(
            method="tools/call",
            params=mcp_types.CallToolRequestParams(name="_failing_tool", arguments={"x": "boom"}),
        )
        handler = server.request_handlers[mcp_types.CallToolRequest]
        result = await handler(req)

        call_result = result.root
        assert isinstance(call_result, mcp_types.CallToolResult)
        assert call_result.isError is True
        assert "intentional failure" in call_result.content[0].text

    @pytest.mark.asyncio
    async def test_server_name(self):
        server = create_mcp_server_from_tools("my-server", [self._make_add_tool()])
        assert server.name == "my-server"

    @pytest.mark.asyncio
    async def test_empty_tools_list(self):
        server = create_mcp_server_from_tools("empty", [])

        from mcp import types as mcp_types

        handler = server.request_handlers[mcp_types.ListToolsRequest]
        result = await handler(None)
        assert result.root.tools == []
