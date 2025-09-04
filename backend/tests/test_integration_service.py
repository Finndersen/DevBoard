"""Test integration service functionality."""

from unittest.mock import AsyncMock, patch

import pytest

from devboard.integrations.base import IntegrationConfigurationError
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
    @patch("devboard.services.integration_service.IntegrationRegistry.get_integration_class")
    async def test_test_integration_connection_config_error(self, mock_get_class):
        """Test handling of configuration errors."""
        # Mock integration class that raises config error
        mock_integration_class = AsyncMock()
        mock_integration_class.create.side_effect = IntegrationConfigurationError("Missing config")
        mock_get_class.return_value = mock_integration_class

        result = await self.service.test_integration_connection("github")

        assert not result.success
        assert result.integration_type == "github"
        assert result.error_type == "config_error"
        assert "Missing config" in result.error_message

    @pytest.mark.asyncio
    @patch("devboard.services.integration_service.IntegrationRegistry.get_integration_class")
    async def test_test_integration_connection_success(self, mock_get_class):
        """Test successful connection test."""
        # Mock integration instance and class
        mock_integration = AsyncMock()
        mock_integration.test_connection.return_value = True

        mock_integration_class = AsyncMock()
        mock_integration_class.create.return_value = mock_integration
        mock_get_class.return_value = mock_integration_class

        result = await self.service.test_integration_connection("github")

        assert result.success
        assert result.integration_type == "github"
        assert result.error_type is None
        assert result.error_message is None

        mock_integration_class.create.assert_called_once()
        mock_integration.test_connection.assert_called_once()

    @pytest.mark.asyncio
    @patch("devboard.services.integration_service.IntegrationRegistry.get_integration_class")
    async def test_test_integration_connection_failure(self, mock_get_class):
        """Test failed connection test."""
        # Mock integration instance and class
        mock_integration = AsyncMock()
        mock_integration.test_connection.return_value = False

        mock_integration_class = AsyncMock()
        mock_integration_class.create.return_value = mock_integration
        mock_get_class.return_value = mock_integration_class

        result = await self.service.test_integration_connection("github")

        assert not result.success
        assert result.integration_type == "github"
        assert result.error_type == "connection_error"
        assert "Connection test failed" in result.error_message

    @pytest.mark.asyncio
    @patch("devboard.services.integration_service.IntegrationRegistry.get_available_types")
    @patch.object(IntegrationService, "test_integration_connection")
    async def test_test_all_integrations(self, mock_test_single, mock_get_types):
        """Test testing all integrations."""
        mock_get_types.return_value = ["github", "jira"]

        # Mock results for each integration
        github_result = IntegrationTestResult("github", True)
        jira_result = IntegrationTestResult("jira", False, "Config error", "config_error")
        mock_test_single.side_effect = [github_result, jira_result]

        results = await self.service.test_all_integrations()

        assert len(results) == 2
        assert results["github"].success
        assert not results["jira"].success
        assert results["jira"].error_type == "config_error"
