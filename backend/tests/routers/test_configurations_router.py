"""Tests for configurations router."""

import pytest
from unittest.mock import Mock

from devboard.api.dependencies.services import get_config_service
from devboard.api.main import app


@pytest.fixture
def test_config_data():
    """Sample configuration data for testing."""
    return {"key": "test.config.key", "value_json": '{"test": "value"}'}


@pytest.fixture
def mock_config_service():
    """Mock config service for testing."""
    return Mock()


@pytest.fixture
def client_with_mock_config_service(client, mock_config_service):
    """Client with mocked config service."""
    app.dependency_overrides[get_config_service] = lambda: mock_config_service
    yield client
    # Clean up after test
    if get_config_service in app.dependency_overrides:
        del app.dependency_overrides[get_config_service]


class TestConfigurationsRouter:
    """Test configurations router endpoints."""

    def test_list_configurations_empty(self, client_with_mock_config_service, mock_config_service):
        """Test listing configurations when none exist."""
        mock_config_service.list_configs.return_value = []

        response = client_with_mock_config_service.get("/api/configurations/")
        assert response.status_code == 200
        assert response.json() == []
        mock_config_service.list_configs.assert_called_once_with(prefix=None)

    def test_list_configurations_with_data(self, client_with_mock_config_service, mock_config_service):
        """Test listing configurations with existing data."""
        mock_config_service.list_configs.return_value = ["test.config.key", "another.config"]

        response = client_with_mock_config_service.get("/api/configurations/")
        assert response.status_code == 200
        configs = response.json()
        assert len(configs) == 2
        assert "test.config.key" in configs
        assert "another.config" in configs

    def test_get_configuration_detail_success(self, client_with_mock_config_service, mock_config_service):
        """Test getting detailed configuration information."""
        mock_response = {
            "key": "test.config.key",
            "fields": [
                {
                    "name": "test_field",
                    "type": "string",
                    "required": True,
                    "env_value": "env_test_value",
                    "db_value": None,
                    "default_value": None,
                    "is_secret": False,
                    "env_var_name": "TEST_FIELD",
                }
            ],
            "validation_status": "valid",
            "validation_errors": None,
        }
        mock_config_service.get_config_details_by_key.return_value = type("MockResponse", (), mock_response)()

        response = client_with_mock_config_service.get("/api/configurations/test.config.key/detail")
        assert response.status_code == 200
        config_data = response.json()
        assert config_data["key"] == "test.config.key"
        assert len(config_data["fields"]) == 1
        assert config_data["fields"][0]["name"] == "test_field"

    def test_get_configuration_detail_not_found(self, client_with_mock_config_service, mock_config_service):
        """Test getting details for non-existent configuration."""
        mock_response = {
            "key": "nonexistent.key",
            "fields": [],
            "validation_status": "unconfigured",
            "validation_errors": ["No schema registered for key: nonexistent.key"],
        }
        mock_config_service.get_config_details_by_key.return_value = type("MockResponse", (), mock_response)()

        response = client_with_mock_config_service.get("/api/configurations/nonexistent.key/detail")
        assert response.status_code == 404

    def test_update_configuration_success(self, client_with_mock_config_service, mock_config_service):
        """Test updating configuration with complete structure."""
        mock_response = {
            "key": "test.config.key",
            "fields": [
                {
                    "name": "test_field",
                    "type": "string",
                    "required": True,
                    "env_value": None,
                    "db_value": "new_value",
                    "default_value": None,
                    "is_secret": False,
                    "env_var_name": "TEST_FIELD",
                }
            ],
            "validation_status": "valid",
            "validation_errors": None,
        }
        mock_config_service.update_configuration.return_value = type("MockResponse", (), mock_response)()

        config_data = {"test_field": "new_value", "another_field": None}
        response = client_with_mock_config_service.patch("/api/configurations/test.config.key", json=config_data)

        assert response.status_code == 200
        mock_config_service.update_configuration.assert_called_once_with("test.config.key", config_data)

    def test_update_configuration_schema_not_found(self, client_with_mock_config_service, mock_config_service):
        """Test updating configuration with non-existent schema."""
        mock_config_service.update_configuration.side_effect = ValueError("No schema registered for key: invalid.key")

        response = client_with_mock_config_service.patch("/api/configurations/invalid.key", json={"field": "value"})
        assert response.status_code == 404
        assert "No schema registered" in response.json()["detail"]

    def test_delete_configuration_success(self, client_with_mock_config_service, mock_config_service):
        """Test deleting a configuration."""
        mock_config_service.delete_config.return_value = None  # delete_config doesn't return anything on success

        response = client_with_mock_config_service.delete("/api/configurations/test.config.key")
        assert response.status_code == 200
        assert response.json()["message"] == "Configuration deleted successfully"
        mock_config_service.delete_config.assert_called_once_with("test.config.key")

    def test_delete_configuration_not_found(self, client_with_mock_config_service, mock_config_service):
        """Test deleting a non-existent configuration."""
        mock_config_service.delete_config.side_effect = Exception("Not found")

        response = client_with_mock_config_service.delete("/api/configurations/nonexistent.key")
        assert response.status_code == 404
        assert response.json()["detail"] == "Configuration not found"
