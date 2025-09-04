"""Test settings router functionality."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from devboard.api.main import app
from devboard.services.integration_service import IntegrationTestResult


class TestSettingsRouter:
    """Test cases for Settings Router."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

    @patch("devboard.api.routers.settings.IntegrationService")
    def test_test_integration_connection_success(self, mock_service_class):
        """Test successful integration connection test."""
        # Mock the service
        mock_service = AsyncMock()
        mock_result = IntegrationTestResult(
            integration_type="github", success=True, error_message=None, error_type=None
        )
        mock_service.test_integration_connection.return_value = mock_result
        mock_service_class.return_value = mock_service

        response = self.client.post("/api/settings/integrations/github/test")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_type"] == "github"
        assert data["success"] is True
        assert data["error_message"] is None
        assert data["error_type"] is None

    @patch("devboard.api.routers.settings.IntegrationService")
    def test_test_integration_connection_config_error(self, mock_service_class):
        """Test integration connection test with config error."""
        # Mock the service
        mock_service = AsyncMock()
        mock_result = IntegrationTestResult(
            integration_type="github",
            success=False,
            error_message="GitHub configuration error: Missing API token",
            error_type="config_error",
        )
        mock_service.test_integration_connection.return_value = mock_result
        mock_service_class.return_value = mock_service

        response = self.client.post("/api/settings/integrations/github/test")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_type"] == "github"
        assert data["success"] is False
        assert "Missing API token" in data["error_message"]
        assert data["error_type"] == "config_error"

    @patch("devboard.api.routers.settings.IntegrationService")
    def test_test_integration_connection_unsupported(self, mock_service_class):
        """Test integration connection test with unsupported integration."""
        # Mock the service
        mock_service = AsyncMock()
        mock_result = IntegrationTestResult(
            integration_type="unknown",
            success=False,
            error_message="Unsupported integration type: unknown",
            error_type="unsupported_integration",
        )
        mock_service.test_integration_connection.return_value = mock_result
        mock_service_class.return_value = mock_service

        response = self.client.post("/api/settings/integrations/unknown/test")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Unsupported integration type: unknown"
