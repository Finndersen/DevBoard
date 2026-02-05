"""Unit tests for MCP server configuration service."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.api.schemas.mcp import VerifyResult
from devboard.api.schemas.oauth import MCPServerConfigCreate, MCPServerConfigUpdate
from devboard.db.models.mcp_server import (
    HttpMCPConfig,
    MCPServerConfig,
    MCPServerType,
    StdioMCPConfig,
)
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
    config.config_json = '{"command": "npx", "args": ["-y", "@test/server"]}'
    return config


@pytest.fixture
def sample_http_config():
    """Create a sample HTTP MCP server configuration."""
    config = Mock(spec=MCPServerConfig)
    config.id = 2
    config.name = "Test HTTP Server"
    config.server_type = MCPServerType.HTTP
    config.config_json = '{"url": "https://mcp.example.com", "auth_type": "bearer", "bearer_token": "secret"}'
    return config


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
        """Test verifying a server that doesn't exist."""
        mock_repository.get_by_id.return_value = None

        result = await mcp_service.verify(999)

        assert isinstance(result, VerifyResult)
        assert result.success is False
        assert result.error == "Server not found"
        assert result.tools is None

    @pytest.mark.asyncio
    async def test_verify_success(self, mcp_service, mock_repository, sample_stdio_config):
        """Test successful verification returning tools."""
        mock_repository.get_by_id.return_value = sample_stdio_config

        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object"}

        mock_session = AsyncMock()
        mock_list_result = Mock()
        mock_list_result.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_list_result

        with patch("devboard.services.mcp_service.create_mcp_lifecycle_manager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.return_value = mock_session
            mock_lifecycle.__aexit__.return_value = None
            mock_create_lifecycle.return_value = mock_lifecycle

            result = await mcp_service.verify(1)

        assert isinstance(result, VerifyResult)
        assert result.success is True
        assert result.error is None
        assert result.tools is not None
        assert len(result.tools) == 1
        assert result.tools[0].name == "test_tool"
        assert result.tools[0].description == "A test tool"

    @pytest.mark.asyncio
    async def test_verify_connection_failure(self, mcp_service, mock_repository, sample_stdio_config):
        """Test verification when connection fails."""
        mock_repository.get_by_id.return_value = sample_stdio_config

        with patch("devboard.services.mcp_service.create_mcp_lifecycle_manager") as mock_create_lifecycle:
            mock_lifecycle = AsyncMock()
            mock_lifecycle.__aenter__.side_effect = ConnectionError("Failed to connect")
            mock_create_lifecycle.return_value = mock_lifecycle

            result = await mcp_service.verify(1)

        assert isinstance(result, VerifyResult)
        assert result.success is False
        assert result.error is not None and "Failed to connect" in result.error
        assert result.tools is None
