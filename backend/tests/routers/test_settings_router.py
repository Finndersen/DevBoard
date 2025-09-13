"""Test settings router functionality."""

from unittest.mock import AsyncMock

import pytest

from devboard.api.dependencies.services import get_integration_service
from devboard.api.main import app
from devboard.services.integration_service import IntegrationTestResult


@pytest.fixture
def mock_integration_service():
    """Mock integration service for testing."""
    return AsyncMock()


@pytest.fixture
def client_with_mock_integration_service(client, mock_integration_service):
    """Client with mocked integration service."""
    app.dependency_overrides[get_integration_service] = lambda: mock_integration_service
    yield client
    # Clean up after test
    if get_integration_service in app.dependency_overrides:
        del app.dependency_overrides[get_integration_service]


class TestSettingsRouter:
    """Test cases for Settings Router."""

    def test_test_integration_connection_success(self, client_with_mock_integration_service, mock_integration_service):
        """Test successful integration connection test."""
        mock_result = IntegrationTestResult(
            integration_type="github", success=True, error_message=None, error_type=None
        )
        mock_integration_service.test_integration_connection.return_value = mock_result

        response = client_with_mock_integration_service.post("/api/settings/integrations/github/test")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_type"] == "github"
        assert data["success"] is True
        assert data["error_message"] is None
        assert data["error_type"] is None

    def test_test_integration_connection_config_error(self, client_with_mock_integration_service, mock_integration_service):
        """Test integration connection test with config error."""
        mock_result = IntegrationTestResult(
            integration_type="github",
            success=False,
            error_message="GitHub configuration error: Missing API token",
            error_type="config_error",
        )
        mock_integration_service.test_integration_connection.return_value = mock_result

        response = client_with_mock_integration_service.post("/api/settings/integrations/github/test")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_type"] == "github"
        assert data["success"] is False
        assert "Missing API token" in data["error_message"]
        assert data["error_type"] == "config_error"

    def test_test_integration_connection_unsupported(self, client_with_mock_integration_service, mock_integration_service):
        """Test integration connection test with unsupported integration."""
        mock_result = IntegrationTestResult(
            integration_type="unknown",
            success=False,
            error_message="Unsupported integration type: unknown",
            error_type="unsupported_integration",
        )
        mock_integration_service.test_integration_connection.return_value = mock_result

        response = client_with_mock_integration_service.post("/api/settings/integrations/unknown/test")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Unsupported integration type: unknown"
