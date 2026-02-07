"""Unit tests for MCP tool factory."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.db.models import MCPServerConfig, MCPTool
from devboard.mcp.exceptions import MCPToolExecutionError
from devboard.mcp.mcp_tool_factory import MCPToolFactory


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
        mock_text_content = Mock()
        mock_text_content.text = "Authentication required"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text_content]
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
        mock_text_content = Mock()
        mock_text_content.text = "Success result"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text_content]
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
        mock_text1 = Mock()
        mock_text1.text = "Error line 1"
        mock_text2 = Mock()
        mock_text2.text = "Error line 2"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text1, mock_text2]
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
