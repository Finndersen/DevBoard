"""Test integration service functionality."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.core.registry import Registry
from devboard.integrations.base import BaseIntegration, IntegrationConfigurationError, IntegrationConnectionResult
from devboard.services.integration_service import IntegrationService, IntegrationTestResult


@pytest.fixture
def mock_config_repository():
    """Mock configuration repository."""
    return Mock()


class TestIntegrationService:
    """Test cases for IntegrationService."""

    @pytest.mark.asyncio
    async def test_test_integration_connection_unsupported_type(self, mock_config_repository):
        """Test handling of unsupported integration type."""
        service = IntegrationService(mock_config_repository)
        result = await service.test_integration_connection("unknown")

        assert not result.success
        assert result.integration_type == "unknown"
        assert result.error_type == "unsupported_integration"
        assert "Unsupported integration type" in result.error_message

    @pytest.mark.asyncio
    async def test_test_integration_connection_config_error(self, mock_config_repository):
        """Test handling of configuration errors."""
        # Mock integration class that raises config error during init
        mock_integration_class = Mock()
        mock_integration_class.side_effect = IntegrationConfigurationError("Missing config")
        mock_integration_class.integration_type = "github"

        # Create test registry with mock integration
        test_registry = Registry[type[BaseIntegration]]([mock_integration_class], key_attr="integration_type")
        service = IntegrationService(mock_config_repository, test_registry)

        # Mock the config service get_config call to return a mock config
        mock_config = Mock()
        with patch("devboard.services.integration_service.ConfigService") as mock_config_service_class:
            mock_config_service = Mock()
            mock_config_service.get_config.return_value = mock_config
            mock_config_service_class.return_value = mock_config_service

            result = await service.test_integration_connection("github")

        assert not result.success
        assert result.integration_type == "github"
        assert result.error_type == "config_error"
        assert "Missing config" in result.error_message

    @pytest.mark.asyncio
    async def test_test_integration_connection_success(self, mock_config_repository):
        """Test successful connection test."""
        # Mock integration instance and class
        mock_integration = AsyncMock()
        mock_integration.test_connection.return_value = IntegrationConnectionResult(
            success=True, message="Connection successful"
        )

        mock_integration_class = Mock()
        mock_integration_class.return_value = mock_integration
        mock_integration_class.integration_type = "github"

        # Create test registry with mock integration
        test_registry = Registry[type[BaseIntegration]]([mock_integration_class], key_attr="integration_type")
        service = IntegrationService(mock_config_repository, test_registry)

        # Mock the config service get_config call to return a mock config
        mock_config = Mock()
        with patch("devboard.services.integration_service.ConfigService") as mock_config_service_class:
            mock_config_service = Mock()
            mock_config_service.get_config.return_value = mock_config
            mock_config_service_class.return_value = mock_config_service

            result = await service.test_integration_connection("github")

        assert result.success
        assert result.integration_type == "github"
        assert result.error_type is None
        assert result.error_message is None

        mock_integration_class.assert_called_once_with(mock_config)
        mock_integration.test_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_integration_connection_failure(self, mock_config_repository):
        """Test failed connection test."""
        # Mock integration instance and class
        mock_integration = AsyncMock()
        mock_integration.test_connection.return_value = IntegrationConnectionResult(
            success=False, message="Connection failed"
        )

        mock_integration_class = Mock()
        mock_integration_class.return_value = mock_integration
        mock_integration_class.integration_type = "github"

        # Create test registry with mock integration
        test_registry = Registry[type[BaseIntegration]]([mock_integration_class], key_attr="integration_type")
        service = IntegrationService(mock_config_repository, test_registry)

        # Mock the config service get_config call to return a mock config
        mock_config = Mock()
        with patch("devboard.services.integration_service.ConfigService") as mock_config_service_class:
            mock_config_service = Mock()
            mock_config_service.get_config.return_value = mock_config
            mock_config_service_class.return_value = mock_config_service

            result = await service.test_integration_connection("github")

        assert not result.success
        assert result.integration_type == "github"
        assert result.error_type == "connection_error"
        assert "Connection failed" in result.error_message

    @pytest.mark.asyncio
    async def test_test_all_integrations(self, mock_config_repository):
        """Test testing all integrations."""
        # Create mock integration classes
        github_integration_class = AsyncMock()
        github_integration_class.integration_type = "github"
        jira_integration_class = AsyncMock()
        jira_integration_class.integration_type = "jira"

        # Create test registry with both integrations
        test_registry = Registry[type[BaseIntegration]](
            [github_integration_class, jira_integration_class], key_attr="integration_type"
        )
        service = IntegrationService(mock_config_repository, test_registry)

        # Mock the test_integration_connection method to return predefined results
        github_result = IntegrationTestResult("github", True)
        jira_result = IntegrationTestResult("jira", False, "Config error", "config_error")
        service.test_integration_connection = AsyncMock(side_effect=[github_result, jira_result])

        results = await service.test_all_integrations()

        assert len(results) == 2
        assert results["github"].success
        assert not results["jira"].success
        assert results["jira"].error_type == "config_error"
