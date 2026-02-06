"""Unit tests for MCP tool factory."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.mcp.exceptions import MCPToolExecutionError
from devboard.mcp.mcp_tool_factory import MCPToolFactory


@pytest.fixture
def mock_server_config():
    """Create a mock MCP server configuration."""
    config = Mock()
    config.id = 1
    config.name = "Test Server"
    return config


@pytest.fixture
def mock_mcp_tool():
    """Create a mock MCP tool from list_tools."""
    tool = Mock()
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.inputSchema = {"type": "object", "properties": {"param": {"type": "string"}}}
    return tool


class TestMCPToolFactoryErrorHandling:
    """Tests for MCP tool factory error propagation."""

    @pytest.mark.asyncio
    async def test_tool_wrapper_raises_error_when_is_error_true(self, mock_server_config, mock_mcp_tool):
        """Test that wrapped tool raises MCPToolExecutionError when isError is True."""
        mock_text_content = Mock()
        mock_text_content.text = "Authentication required"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text_content]
        mock_call_result.isError = True

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = Mock(tools=[mock_mcp_tool])
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.setup.return_value = mock_session
            mock_lifecycle_class.return_value = mock_lifecycle

            factory = MCPToolFactory([mock_server_config])
            async with factory:
                tools = factory.get_tools()
                assert len(tools) == 1

                with pytest.raises(MCPToolExecutionError, match="Authentication required"):
                    await tools[0].function(param="test")

    @pytest.mark.asyncio
    async def test_tool_wrapper_raises_default_error_when_empty_content(self, mock_server_config, mock_mcp_tool):
        """Test that wrapped tool uses default error message when content is empty."""
        mock_call_result = Mock()
        mock_call_result.content = []
        mock_call_result.isError = True

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = Mock(tools=[mock_mcp_tool])
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.setup.return_value = mock_session
            mock_lifecycle_class.return_value = mock_lifecycle

            factory = MCPToolFactory([mock_server_config])
            async with factory:
                tools = factory.get_tools()

                with pytest.raises(MCPToolExecutionError, match="MCP tool execution failed"):
                    await tools[0].function(param="test")

    @pytest.mark.asyncio
    async def test_tool_wrapper_returns_result_when_not_error(self, mock_server_config, mock_mcp_tool):
        """Test that wrapped tool returns content when isError is False."""
        mock_text_content = Mock()
        mock_text_content.text = "Success result"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text_content]
        mock_call_result.isError = False

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = Mock(tools=[mock_mcp_tool])
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.setup.return_value = mock_session
            mock_lifecycle_class.return_value = mock_lifecycle

            factory = MCPToolFactory([mock_server_config])
            async with factory:
                tools = factory.get_tools()
                result = await tools[0].function(param="test")

        assert result == "Success result"

    @pytest.mark.asyncio
    async def test_tool_wrapper_joins_multiple_text_parts_in_error(self, mock_server_config, mock_mcp_tool):
        """Test that multiple text parts are joined in error message."""
        mock_text1 = Mock()
        mock_text1.text = "Error line 1"
        mock_text2 = Mock()
        mock_text2.text = "Error line 2"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text1, mock_text2]
        mock_call_result.isError = True

        mock_session = AsyncMock()
        mock_session.list_tools.return_value = Mock(tools=[mock_mcp_tool])
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.mcp.mcp_tool_factory.MCPLifecycleManager") as mock_lifecycle_class:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.setup.return_value = mock_session
            mock_lifecycle_class.return_value = mock_lifecycle

            factory = MCPToolFactory([mock_server_config])
            async with factory:
                tools = factory.get_tools()

                with pytest.raises(MCPToolExecutionError, match="Error line 1\nError line 2"):
                    await tools[0].function(param="test")
