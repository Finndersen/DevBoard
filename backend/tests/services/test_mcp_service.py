"""Unit tests for MCP server configuration service."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.api.schemas.mcp import MCPServerDetailResponse, MCPToolUpdate
from devboard.api.schemas.oauth import MCPServerConfigCreate, MCPServerConfigUpdate
from devboard.db.models.mcp_server import (
    HttpMCPConfig,
    MCPServerConfig,
    MCPServerType,
    MCPTool,
    StdioMCPConfig,
)
from devboard.mcp.exceptions import MCPToolExecutionError
from devboard.services.mcp_service import MCPService


@pytest.fixture
def mock_repository():
    """Create a mock MCPServerRepository."""
    return Mock()


@pytest.fixture
def mcp_service(mock_repository):
    """Create an MCPService instance with mocked repository."""
    return MCPService(mcp_server_repository=mock_repository)


@pytest.fixture
def sample_stdio_config():
    """Create a sample STDIO MCP server configuration."""
    config = Mock(spec=MCPServerConfig)
    config.id = 1
    config.name = "Test STDIO Server"
    config.server_type = MCPServerType.STDIO
    config.config_json = {"command": "npx", "args": ["-y", "@test/server"]}
    config.last_verified_at = None
    config.last_verified_success = None
    config.last_verified_error = None
    config.tools = []
    return config


@pytest.fixture
def sample_http_config():
    """Create a sample HTTP MCP server configuration."""
    config = Mock(spec=MCPServerConfig)
    config.id = 2
    config.name = "Test HTTP Server"
    config.server_type = MCPServerType.HTTP
    config.config_json = {"url": "https://mcp.example.com", "auth_type": "bearer", "bearer_token": "secret"}
    config.last_verified_at = None
    config.last_verified_success = None
    config.last_verified_error = None
    config.tools = []
    return config


@pytest.fixture
def sample_mcp_tool():
    """Create a sample MCP tool."""
    tool = Mock(spec=MCPTool)
    tool.id = 1
    tool.server_id = 1
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.input_schema = {"type": "object", "properties": {"param1": {"type": "string"}}}
    return tool


class TestMCPServiceCRUD:
    """Tests for MCPService CRUD operations."""

    def test_get_all(self, mcp_service, mock_repository, sample_stdio_config):
        """Test retrieving all MCP server configurations."""
        mock_repository.get_all.return_value = [sample_stdio_config]

        result = mcp_service.get_all()

        assert len(result) == 1
        assert result[0] == sample_stdio_config
        mock_repository.get_all.assert_called_once()

    def test_get_by_id_found(self, mcp_service, mock_repository, sample_stdio_config):
        """Test retrieving an MCP server by ID when found."""
        mock_repository.get_by_id.return_value = sample_stdio_config

        result = mcp_service.get_by_id(1)

        assert result == sample_stdio_config
        mock_repository.get_by_id.assert_called_once_with(1)

    def test_get_by_id_not_found(self, mcp_service, mock_repository):
        """Test retrieving an MCP server by ID when not found."""
        mock_repository.get_by_id.return_value = None

        result = mcp_service.get_by_id(999)

        assert result is None
        mock_repository.get_by_id.assert_called_once_with(999)

    def test_create_stdio_server(self, mcp_service, mock_repository):
        """Test creating a new STDIO MCP server configuration."""
        create_data = MCPServerConfigCreate(
            name="New Server",
            server_type=MCPServerType.STDIO,
            config_json=StdioMCPConfig(command="test-cmd", args=["--flag"]),
        )

        mock_created = Mock(spec=MCPServerConfig)
        mock_repository.create.return_value = mock_created

        result = mcp_service.create(create_data)

        assert result == mock_created
        mock_repository.create.assert_called_once()
        created_config = mock_repository.create.call_args[0][0]
        assert created_config.name == "New Server"
        assert created_config.server_type == MCPServerType.STDIO

    def test_create_http_server(self, mcp_service, mock_repository):
        """Test creating a new HTTP MCP server configuration."""
        create_data = MCPServerConfigCreate(
            name="HTTP Server",
            server_type=MCPServerType.HTTP,
            config_json=HttpMCPConfig(url="https://example.com/mcp", auth_type="none"),
        )

        mock_created = Mock(spec=MCPServerConfig)
        mock_repository.create.return_value = mock_created

        result = mcp_service.create(create_data)

        assert result == mock_created
        mock_repository.create.assert_called_once()

    def test_update_name(self, mcp_service, mock_repository, sample_stdio_config):
        """Test updating an MCP server's name."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.update.return_value = sample_stdio_config

        update_data = MCPServerConfigUpdate(name="Updated Name")

        result = mcp_service.update(1, update_data)

        assert result is not None
        assert sample_stdio_config.name == "Updated Name"
        mock_repository.update.assert_called_once_with(sample_stdio_config)

    def test_update_not_found(self, mcp_service, mock_repository):
        """Test updating an MCP server that doesn't exist."""
        mock_repository.get_by_id.return_value = None

        update_data = MCPServerConfigUpdate(name="Updated Name")

        result = mcp_service.update(999, update_data)

        assert result is None
        mock_repository.update.assert_not_called()

    def test_delete_success(self, mcp_service, mock_repository):
        """Test deleting an MCP server configuration."""
        mock_repository.delete.return_value = True

        result = mcp_service.delete(1)

        assert result is True
        mock_repository.delete.assert_called_once_with(1)

    def test_delete_not_found(self, mcp_service, mock_repository):
        """Test deleting an MCP server that doesn't exist."""
        mock_repository.delete.return_value = False

        result = mcp_service.delete(999)

        assert result is False


class TestMCPServiceVerify:
    """Tests for MCPService verify operation."""

    @pytest.mark.asyncio
    async def test_verify_server_not_found(self, mcp_service, mock_repository):
        """Test verifying a server that doesn't exist raises ValueError."""
        mock_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Server not found"):
            await mcp_service.verify(999)

    @pytest.mark.asyncio
    async def test_verify_success(self, mcp_service, mock_repository, sample_stdio_config):
        """Test successful verification syncs tools and returns server detail."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_by_id_with_tools.return_value = sample_stdio_config
        mock_repository.get_tools_by_server_id.return_value = []

        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object"}

        mock_session = AsyncMock()
        mock_list_result = Mock()
        mock_list_result.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_list_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            result = await mcp_service.verify(1)

        assert isinstance(result, MCPServerDetailResponse)
        # Verify status was updated
        assert sample_stdio_config.last_verified_success is True
        assert sample_stdio_config.last_verified_error is None
        mock_repository.update.assert_called_once()
        # Verify new tool was created (since cache was empty)
        mock_repository.create_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_connection_failure(self, mcp_service, mock_repository, sample_stdio_config):
        """Test verification when connection fails updates status."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_by_id_with_tools.return_value = sample_stdio_config

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.side_effect = ConnectionError("Failed to connect")
            mock_create_lifecycle.return_value = mock_lifecycle

            result = await mcp_service.verify(1)

        assert isinstance(result, MCPServerDetailResponse)
        assert sample_stdio_config.last_verified_success is False
        assert "Failed to connect" in sample_stdio_config.last_verified_error
        mock_repository.update.assert_called_once()


class TestMCPServiceToolSync:
    """Tests for MCPService tool sync operations."""

    @pytest.mark.asyncio
    async def test_sync_creates_new_tools(self, mcp_service, mock_repository, sample_stdio_config):
        """Test that sync creates new tools when cache is empty."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_by_id_with_tools.return_value = sample_stdio_config
        mock_repository.get_tools_by_server_id.return_value = []

        mock_tool1 = Mock()
        mock_tool1.name = "tool1"
        mock_tool1.description = "Tool 1"
        mock_tool1.inputSchema = {"type": "object"}

        mock_tool2 = Mock()
        mock_tool2.name = "tool2"
        mock_tool2.description = "Tool 2"
        mock_tool2.inputSchema = None

        mock_session = AsyncMock()
        mock_list_result = Mock()
        mock_list_result.tools = [mock_tool1, mock_tool2]
        mock_session.list_tools.return_value = mock_list_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            await mcp_service.verify(1)

        # Verify two new tools were created
        assert mock_repository.create_tool.call_count == 2
        created_tools = [call[0][0] for call in mock_repository.create_tool.call_args_list]
        created_names = {t.name for t in created_tools}
        assert created_names == {"tool1", "tool2"}

    @pytest.mark.asyncio
    async def test_sync_skips_existing_tools(self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool):
        """Test that sync skips existing tools (doesn't update them)."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_by_id_with_tools.return_value = sample_stdio_config
        # Existing tool in cache
        mock_repository.get_tools_by_server_id.return_value = [sample_mcp_tool]

        # Server returns same tool with different description
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Updated description"
        mock_tool.inputSchema = {"type": "object"}

        mock_session = AsyncMock()
        mock_list_result = Mock()
        mock_list_result.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_list_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            await mcp_service.verify(1)

        # No new tools created (existing tool was skipped)
        mock_repository.create_tool.assert_not_called()
        # No tools deleted (tool still exists on server)
        mock_repository.delete_tools_by_ids.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_deletes_stale_tools(self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool):
        """Test that sync deletes tools no longer returned by server."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_by_id_with_tools.return_value = sample_stdio_config
        # Existing tool in cache
        mock_repository.get_tools_by_server_id.return_value = [sample_mcp_tool]

        # Server returns empty list (tool removed from server)
        mock_session = AsyncMock()
        mock_list_result = Mock()
        mock_list_result.tools = []
        mock_session.list_tools.return_value = mock_list_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            await mcp_service.verify(1)

        # Stale tool was deleted
        mock_repository.delete_tools_by_ids.assert_called_once_with([sample_mcp_tool.id])

    @pytest.mark.asyncio
    async def test_sync_handles_mixed_scenario(self, mcp_service, mock_repository, sample_stdio_config):
        """Test sync with mix of new, existing, and stale tools."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_by_id_with_tools.return_value = sample_stdio_config

        # Existing tools in cache
        existing_tool1 = Mock(spec=MCPTool)
        existing_tool1.id = 1
        existing_tool1.name = "existing_tool"
        stale_tool = Mock(spec=MCPTool)
        stale_tool.id = 2
        stale_tool.name = "stale_tool"
        mock_repository.get_tools_by_server_id.return_value = [existing_tool1, stale_tool]

        # Server returns: existing_tool (keep), new_tool (create), no stale_tool (delete)
        mock_existing = Mock()
        mock_existing.name = "existing_tool"
        mock_existing.description = "Existing"
        mock_existing.inputSchema = None

        mock_new = Mock()
        mock_new.name = "new_tool"
        mock_new.description = "New"
        mock_new.inputSchema = {"type": "object"}

        mock_session = AsyncMock()
        mock_list_result = Mock()
        mock_list_result.tools = [mock_existing, mock_new]
        mock_session.list_tools.return_value = mock_list_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            await mcp_service.verify(1)

        # Stale tool deleted
        mock_repository.delete_tools_by_ids.assert_called_once_with([stale_tool.id])
        # New tool created (existing one skipped)
        mock_repository.create_tool.assert_called_once()
        created_tool = mock_repository.create_tool.call_args[0][0]
        assert created_tool.name == "new_tool"


class TestMCPServiceToolUpdate:
    """Tests for MCPService tool update operations."""

    def test_update_tool_description(self, mcp_service, mock_repository, sample_mcp_tool):
        """Test updating a tool's description."""
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool
        mock_repository.update_tool.return_value = sample_mcp_tool

        update_data = MCPToolUpdate(description="Updated description")
        result = mcp_service.update_tool(1, 1, update_data)

        assert result == sample_mcp_tool
        assert sample_mcp_tool.description == "Updated description"
        mock_repository.update_tool.assert_called_once()

    def test_update_tool_not_found(self, mcp_service, mock_repository):
        """Test updating a tool that doesn't exist."""
        mock_repository.get_tool_by_id.return_value = None

        update_data = MCPToolUpdate(description="New description")
        result = mcp_service.update_tool(1, 999, update_data)

        assert result is None
        mock_repository.update_tool.assert_not_called()

    def test_update_tool_wrong_server(self, mcp_service, mock_repository, sample_mcp_tool):
        """Test updating a tool that belongs to a different server."""
        sample_mcp_tool.server_id = 2  # Tool belongs to server 2
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        update_data = MCPToolUpdate(description="New description")
        result = mcp_service.update_tool(1, 1, update_data)  # Trying to update via server 1

        assert result is None
        mock_repository.update_tool.assert_not_called()


class TestMCPServiceRunTool:
    """Tests for MCPService run_tool operation."""

    @pytest.mark.asyncio
    async def test_run_tool_server_not_found(self, mcp_service, mock_repository):
        """Test running a tool when server doesn't exist raises ValueError."""
        mock_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match="Server not found"):
            await mcp_service.run_tool(999, 1, {"param": "value"})

    @pytest.mark.asyncio
    async def test_run_tool_tool_not_found(self, mcp_service, mock_repository, sample_stdio_config):
        """Test running a tool that doesn't exist raises ValueError."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_tool_by_id.return_value = None

        with pytest.raises(ValueError, match="Tool not found"):
            await mcp_service.run_tool(1, 999, {"param": "value"})

    @pytest.mark.asyncio
    async def test_run_tool_wrong_server(self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool):
        """Test running a tool that belongs to a different server raises ValueError."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        sample_mcp_tool.server_id = 2  # Tool belongs to different server
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        with pytest.raises(ValueError, match="Tool not found"):
            await mcp_service.run_tool(1, 1, {"param": "value"})

    @pytest.mark.asyncio
    async def test_run_tool_success_with_text_content(
        self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool
    ):
        """Test successful tool execution returning text content."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        mock_text_content = Mock()
        mock_text_content.text = "Tool result text"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text_content]
        mock_call_result.isError = False

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            result = await mcp_service.run_tool(1, 1, {"param": "value"})

        assert result == "Tool result text"
        mock_session.call_tool.assert_called_once_with("test_tool", arguments={"param": "value"})

    @pytest.mark.asyncio
    async def test_run_tool_success_with_multiple_text_parts(
        self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool
    ):
        """Test successful tool execution returning multiple text parts."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        mock_text_content1 = Mock()
        mock_text_content1.text = "Part 1"
        mock_text_content2 = Mock()
        mock_text_content2.text = "Part 2"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text_content1, mock_text_content2]
        mock_call_result.isError = False

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            result = await mcp_service.run_tool(1, 1, None)

        assert result == "Part 1\nPart 2"
        mock_session.call_tool.assert_called_once_with("test_tool", arguments={})

    @pytest.mark.asyncio
    async def test_run_tool_success_empty_content(
        self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool
    ):
        """Test successful tool execution with empty content."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        mock_call_result = Mock()
        mock_call_result.content = []
        mock_call_result.isError = False

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            result = await mcp_service.run_tool(1, 1, None)

        assert result == ""

    @pytest.mark.asyncio
    async def test_run_tool_connection_error(self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool):
        """Test tool execution when connection fails propagates the exception."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.side_effect = ConnectionError("Failed to connect")
            mock_create_lifecycle.return_value = mock_lifecycle

            with pytest.raises(ConnectionError, match="Failed to connect"):
                await mcp_service.run_tool(1, 1, {"param": "value"})

    @pytest.mark.asyncio
    async def test_run_tool_execution_error(self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool):
        """Test tool execution when the tool call fails propagates the exception."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        mock_session = AsyncMock()
        mock_session.call_tool.side_effect = RuntimeError("Tool execution failed")

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            with pytest.raises(RuntimeError, match="Tool execution failed"):
                await mcp_service.run_tool(1, 1, {"param": "value"})

    @pytest.mark.asyncio
    async def test_run_tool_mcp_error_response(
        self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool
    ):
        """Test that isError flag in MCP response raises MCPToolExecutionError."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        mock_text_content = Mock()
        mock_text_content.text = "Client must be authenticated to access this resource"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text_content]
        mock_call_result.isError = True

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            with pytest.raises(MCPToolExecutionError, match="Client must be authenticated"):
                await mcp_service.run_tool(1, 1, {"param": "value"})

    @pytest.mark.asyncio
    async def test_run_tool_mcp_error_response_empty_content(
        self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool
    ):
        """Test that isError with empty content uses default error message."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        mock_call_result = Mock()
        mock_call_result.content = []
        mock_call_result.isError = True

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            with pytest.raises(MCPToolExecutionError, match="MCP tool execution failed"):
                await mcp_service.run_tool(1, 1, {"param": "value"})

    @pytest.mark.asyncio
    async def test_run_tool_success_when_not_error(
        self, mcp_service, mock_repository, sample_stdio_config, sample_mcp_tool
    ):
        """Test that isError=False returns content normally."""
        mock_repository.get_by_id.return_value = sample_stdio_config
        mock_repository.get_tool_by_id.return_value = sample_mcp_tool

        mock_text_content = Mock()
        mock_text_content.text = "Success result"

        mock_call_result = Mock()
        mock_call_result.content = [mock_text_content]
        mock_call_result.isError = False

        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_call_result

        with patch("devboard.services.mcp_service.MCPLifecycleManager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            result = await mcp_service.run_tool(1, 1, {"param": "value"})

        assert result == "Success result"
