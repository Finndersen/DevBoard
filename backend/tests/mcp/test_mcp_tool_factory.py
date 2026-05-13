"""Unit tests for MCP tool factory."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from mcp.types import TextContent

from devboard.db.models import MCPServerConfig, MCPTool
from devboard.mcp.exceptions import MCPToolExecutionError
from devboard.mcp.mcp_tool_factory import MCPServerSetupFailure, MCPToolFactory


@pytest.fixture
def mock_server_config():
    """Create a mock MCP server configuration."""
    config = Mock(spec=MCPServerConfig)
    config.id = 1
    config.name = "Test Server"
    config.last_verified_success = True
    return config


@pytest.fixture
def mock_db_mcp_tool(mock_server_config):
    """Create a mock MCPTool database model."""
    tool = Mock(spec=MCPTool)
    tool.id = 1
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.server_id = mock_server_config.id
    tool.server = mock_server_config
    return tool


@pytest.fixture
def mock_mcp_tool_response():
    """Create a mock MCP tool from list_tools response."""
    tool = Mock()
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.inputSchema = {"type": "object", "properties": {"param": {"type": "string"}}}
    return tool


class TestMCPToolFactoryServerFiltering:
    """Tests for MCP tool factory server verification filtering."""

    @pytest.mark.asyncio
    async def test_filters_tools_from_unverified_servers(self):
        """Test that tools from unverified servers are not included."""
        # Create verified server with tool
        verified_server = Mock(spec=MCPServerConfig)
        verified_server.id = 1
        verified_server.name = "Verified Server"
        verified_server.last_verified_success = True

        verified_tool = Mock(spec=MCPTool)
        verified_tool.id = 1
        verified_tool.name = "verified_tool"
        verified_tool.server_id = verified_server.id
        verified_tool.server = verified_server

        # Create unverified server with tool
        unverified_server = Mock(spec=MCPServerConfig)
        unverified_server.id = 2
        unverified_server.name = "Unverified Server"
        unverified_server.last_verified_success = False

        unverified_tool = Mock(spec=MCPTool)
        unverified_tool.id = 2
        unverified_tool.name = "unverified_tool"
        unverified_tool.server_id = unverified_server.id
        unverified_tool.server = unverified_server

        mock_verified_mcp_tool = Mock()
        mock_verified_mcp_tool.name = "verified_tool"
        mock_verified_mcp_tool.description = "A verified tool"

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = Mock(tools=[mock_verified_mcp_tool])

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.mcp_session = mock_session
            mock_lifecycle_class.return_value = mock_lifecycle

            factory = MCPToolFactory([verified_tool, unverified_tool])
            async with factory:
                tools = factory.get_tools()

                # Only the verified server's tool should be included
                assert len(tools) == 1
                assert tools[0].name == "verified_tool"

            # Lifecycle manager should only be created for verified server
            assert mock_lifecycle_class.call_count == 1
            mock_lifecycle_class.assert_called_once_with(verified_server)

    @pytest.mark.asyncio
    async def test_filters_tools_from_never_verified_servers(self):
        """Test that tools from servers never verified (None) are not included."""
        # Create server that was never verified
        never_verified_server = Mock(spec=MCPServerConfig)
        never_verified_server.id = 1
        never_verified_server.name = "Never Verified Server"
        never_verified_server.last_verified_success = None

        tool = Mock(spec=MCPTool)
        tool.id = 1
        tool.name = "test_tool"
        tool.server_id = never_verified_server.id
        tool.server = never_verified_server

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            factory = MCPToolFactory([tool])
            async with factory:
                tools = factory.get_tools()

            # No tools should be included
            assert len(tools) == 0

            # Lifecycle manager should not be created
            assert mock_lifecycle_class.call_count == 0


class TestMCPToolFactoryErrorHandling:
    """Tests for MCP tool factory error propagation."""

    @pytest.mark.asyncio
    async def test_tool_wrapper_raises_error_when_is_error_true(self, mock_db_mcp_tool, mock_mcp_tool_response):
        """Test that wrapped tool raises MCPToolExecutionError when isError is True."""
        mock_call_result = Mock()
        mock_call_result.content = [TextContent(type="text", text="Authentication required")]
        mock_call_result.isError = True

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = Mock(tools=[mock_mcp_tool_response])
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.mcp_session = mock_session
            mock_lifecycle_class.return_value = mock_lifecycle

            factory = MCPToolFactory([mock_db_mcp_tool])
            async with factory:
                tools = factory.get_tools()
                assert len(tools) == 1

                with pytest.raises(MCPToolExecutionError, match="Authentication required"):
                    await tools[0].function(param="test")

    @pytest.mark.asyncio
    async def test_tool_wrapper_raises_default_error_when_empty_content(self, mock_db_mcp_tool, mock_mcp_tool_response):
        """Test that wrapped tool uses default error message when content is empty."""
        mock_call_result = Mock()
        mock_call_result.content = []
        mock_call_result.isError = True

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = Mock(tools=[mock_mcp_tool_response])
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.mcp_session = mock_session
            mock_lifecycle_class.return_value = mock_lifecycle

            factory = MCPToolFactory([mock_db_mcp_tool])
            async with factory:
                tools = factory.get_tools()

                with pytest.raises(MCPToolExecutionError, match="MCP tool execution failed"):
                    await tools[0].function(param="test")

    @pytest.mark.asyncio
    async def test_tool_wrapper_returns_result_when_not_error(self, mock_db_mcp_tool, mock_mcp_tool_response):
        """Test that wrapped tool returns content when isError is False."""
        mock_call_result = Mock()
        mock_call_result.content = [TextContent(type="text", text="Success result")]
        mock_call_result.isError = False

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = Mock(tools=[mock_mcp_tool_response])
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.mcp_session = mock_session
            mock_lifecycle_class.return_value = mock_lifecycle

            factory = MCPToolFactory([mock_db_mcp_tool])
            async with factory:
                tools = factory.get_tools()
                result = await tools[0].function(param="test")

        assert result == "Success result"

    @pytest.mark.asyncio
    async def test_tool_wrapper_joins_multiple_text_parts_in_error(self, mock_db_mcp_tool, mock_mcp_tool_response):
        """Test that multiple text parts are joined in error message."""
        mock_call_result = Mock()
        mock_call_result.content = [
            TextContent(type="text", text="Error line 1"),
            TextContent(type="text", text="Error line 2"),
        ]
        mock_call_result.isError = True

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = Mock(tools=[mock_mcp_tool_response])
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.mcp_session = mock_session
            mock_lifecycle_class.return_value = mock_lifecycle

            factory = MCPToolFactory([mock_db_mcp_tool])
            async with factory:
                tools = factory.get_tools()

                with pytest.raises(MCPToolExecutionError, match="Error line 1\nError line 2"):
                    await tools[0].function(param="test")


class TestMCPToolFactorySetupFailureHandling:
    """Tests for graceful handling of MCP server setup failures."""

    def _make_server_and_tool(self, server_id: int, server_name: str, tool_name: str):
        server = Mock(spec=MCPServerConfig)
        server.id = server_id
        server.name = server_name
        server.last_verified_success = True

        tool = Mock(spec=MCPTool)
        tool.id = server_id * 100
        tool.name = tool_name
        tool.description = f"Tool from {server_name}"
        tool.input_schema = {"type": "object", "properties": {}}
        tool.server_id = server_id
        tool.server = server
        return server, tool

    @pytest.mark.asyncio
    async def test_one_server_fails_other_succeeds(self):
        """When one server fails setup, its tools are skipped but the other server's tools are returned."""
        _, tool_a = self._make_server_and_tool(1, "Failing Server", "tool_a")
        _, tool_b = self._make_server_and_tool(2, "Working Server", "tool_b")

        mock_session = AsyncMock()

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            failing_lifecycle = AsyncMock()
            failing_lifecycle.setup.side_effect = ConnectionError("Connection refused")

            working_lifecycle = AsyncMock()
            working_lifecycle.mcp_session = mock_session

            mock_lifecycle_class.side_effect = [failing_lifecycle, working_lifecycle]

            factory = MCPToolFactory([tool_a, tool_b])
            async with factory:
                tools = factory.get_tools()

                assert len(tools) == 1
                assert tools[0].name == "tool_b"

                assert len(factory.setup_failures) == 1
                assert factory.setup_failures[0] == MCPServerSetupFailure(
                    server_name="Failing Server",
                    server_id=1,
                    error="Connection refused",
                )

    @pytest.mark.asyncio
    async def test_all_servers_fail(self):
        """When all servers fail setup, no tools are returned and all failures recorded."""
        _, tool_a = self._make_server_and_tool(1, "Server A", "tool_a")
        _, tool_b = self._make_server_and_tool(2, "Server B", "tool_b")

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            lifecycle_a = AsyncMock()
            lifecycle_a.setup.side_effect = ConnectionError("refused")

            lifecycle_b = AsyncMock()
            lifecycle_b.setup.side_effect = TimeoutError("timed out")

            mock_lifecycle_class.side_effect = [lifecycle_a, lifecycle_b]

            factory = MCPToolFactory([tool_a, tool_b])
            async with factory:
                assert factory.get_tools() == []
                assert len(factory.setup_failures) == 2
                assert factory.setup_failures[0].server_name == "Server A"
                assert factory.setup_failures[1].server_name == "Server B"

    @pytest.mark.asyncio
    async def test_teardown_only_called_on_successful_servers(self):
        """Failed servers should not have teardown called since they were never added to lifecycle managers."""
        _, tool_a = self._make_server_and_tool(1, "Failing Server", "tool_a")
        _, tool_b = self._make_server_and_tool(2, "Working Server", "tool_b")

        mock_session = AsyncMock()

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            failing_lifecycle = AsyncMock()
            failing_lifecycle.setup.side_effect = ConnectionError("refused")

            working_lifecycle = AsyncMock()
            working_lifecycle.mcp_session = mock_session

            mock_lifecycle_class.side_effect = [failing_lifecycle, working_lifecycle]

            factory = MCPToolFactory([tool_a, tool_b])
            async with factory:
                pass

            working_lifecycle.teardown.assert_called_once()
            failing_lifecycle.teardown.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_tools_from_same_failed_server_all_skipped(self):
        """Multiple tools from the same failed server are all skipped with a single failure entry."""
        server, tool_a = self._make_server_and_tool(1, "Failing Server", "tool_a")
        tool_b = Mock(spec=MCPTool)
        tool_b.id = 101
        tool_b.name = "tool_b"
        tool_b.description = "Another tool from failing server"
        tool_b.input_schema = {"type": "object", "properties": {}}
        tool_b.server_id = server.id
        tool_b.server = server

        _, tool_c = self._make_server_and_tool(2, "Working Server", "tool_c")

        mock_session = AsyncMock()

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            failing_lifecycle = AsyncMock()
            failing_lifecycle.setup.side_effect = ConnectionError("refused")

            working_lifecycle = AsyncMock()
            working_lifecycle.mcp_session = mock_session

            mock_lifecycle_class.side_effect = [failing_lifecycle, working_lifecycle]

            factory = MCPToolFactory([tool_a, tool_b, tool_c])
            async with factory:
                tools = factory.get_tools()

                assert len(tools) == 1
                assert tools[0].name == "tool_c"

                assert len(factory.setup_failures) == 1
                assert factory.setup_failures[0].server_id == 1
