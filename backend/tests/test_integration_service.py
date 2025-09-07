"""Test integration service functionality."""

from unittest.mock import AsyncMock, Mock

import pytest

from devboard.core.registry import Registry
from devboard.integrations.base import BaseIntegration, IntegrationConfigurationError
from devboard.services.integration_service import IntegrationService, IntegrationTestResult


class TestIntegrationService:
    """Test cases for IntegrationService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = IntegrationService()

    @pytest.mark.asyncio
    async def test_test_integration_connection_unsupported_type(self):
        """Test handling of unsupported integration type."""
        result = await self.service.test_integration_connection("unknown")

        assert not result.success
        assert result.integration_type == "unknown"
        assert result.error_type == "unsupported_integration"
        assert "Unsupported integration type" in result.error_message

    @pytest.mark.asyncio
    async def test_test_integration_connection_config_error(self):
        """Test handling of configuration errors."""
        # Mock integration class that raises config error
        mock_integration_class = Mock()
        mock_integration_class.create.side_effect = IntegrationConfigurationError("Missing config")
        mock_integration_class.integration_type = "github"

        # Create test registry with mock integration
        test_registry = Registry[type[BaseIntegration]]([mock_integration_class], key_attr='integration_type')
        service = IntegrationService(test_registry)

        result = await service.test_integration_connection("github")

        assert not result.success
        assert result.integration_type == "github"
        assert result.error_type == "config_error"
        assert "Missing config" in result.error_message

    @pytest.mark.asyncio
    async def test_test_integration_connection_success(self):
        """Test successful connection test."""
        # Mock integration instance and class
        mock_integration = AsyncMock()
        mock_integration.test_connection.return_value = True

        mock_integration_class = Mock()
        mock_integration_class.create.return_value = mock_integration
        mock_integration_class.integration_type = "github"

        # Create test registry with mock integration
        test_registry = Registry[type[BaseIntegration]]([mock_integration_class], key_attr='integration_type')
        service = IntegrationService(test_registry)

        result = await service.test_integration_connection("github")

        assert result.success
        assert result.integration_type == "github"
        assert result.error_type is None
        assert result.error_message is None

        mock_integration_class.create.assert_called_once()
        mock_integration.test_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_integration_connection_failure(self):
        """Test failed connection test."""
        # Mock integration instance and class
        mock_integration = AsyncMock()
        mock_integration.test_connection.return_value = False

        mock_integration_class = Mock()
        mock_integration_class.create.return_value = mock_integration
        mock_integration_class.integration_type = "github"

        # Create test registry with mock integration
        test_registry = Registry[type[BaseIntegration]]([mock_integration_class], key_attr='integration_type')
        service = IntegrationService(test_registry)

        result = await service.test_integration_connection("github")

        assert not result.success
        assert result.integration_type == "github"
        assert result.error_type == "connection_error"
        assert "Connection test failed" in result.error_message

    @pytest.mark.asyncio
    async def test_test_all_integrations(self):
        """Test testing all integrations."""
        # Create mock integration classes
        github_integration_class = AsyncMock()
        github_integration_class.integration_type = "github"
        jira_integration_class = AsyncMock()
        jira_integration_class.integration_type = "jira"

        # Create test registry with both integrations
        test_registry = Registry[type[BaseIntegration]]([
            github_integration_class,
            jira_integration_class
        ], key_attr='integration_type')
        service = IntegrationService(test_registry)

        # Mock the test_integration_connection method to return predefined results
        github_result = IntegrationTestResult("github", True)
        jira_result = IntegrationTestResult("jira", False, "Config error", "config_error")
        service.test_integration_connection = AsyncMock(side_effect=[github_result, jira_result])

        results = await service.test_all_integrations()

        assert len(results) == 2
        assert results["github"].success
        assert not results["jira"].success
        assert results["jira"].error_type == "config_error"
