"""Tests for configurations router."""

from unittest.mock import patch

import pytest


@pytest.fixture
def test_config_data():
    """Sample configuration data for testing."""
    return {"key": "test.config.key", "value_json": '{"test": "value"}'}


class TestConfigurationsRouter:
    """Test configurations router endpoints."""

    @patch("devboard.api.routers.configurations.config_service.list_configs")
    def test_list_configurations_empty(self, mock_list_configs, client):
        """Test listing configurations when none exist."""
        mock_list_configs.return_value = []

        response = client.get("/api/configurations/")
        assert response.status_code == 200
        assert response.json() == []
        mock_list_configs.assert_called_once_with(prefix=None)

    @patch("devboard.api.routers.configurations.config_service.list_configs")
    def test_list_configurations_with_data(self, mock_list_configs, client):
        """Test listing configurations with existing data."""
        mock_list_configs.return_value = ["test.config.key", "another.config"]

        response = client.get("/api/configurations/")
        assert response.status_code == 200
        configs = response.json()
        assert len(configs) == 2
        assert "test.config.key" in configs
        assert "another.config" in configs

    @patch("devboard.api.routers.configurations.config_service.get_config_details")
    def test_get_configuration_detail_success(self, mock_get_details, client):
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
        mock_get_details.return_value = type("MockResponse", (), mock_response)()

        response = client.get("/api/configurations/test.config.key/detail")
        assert response.status_code == 200
        config_data = response.json()
        assert config_data["key"] == "test.config.key"
        assert len(config_data["fields"]) == 1
        assert config_data["fields"][0]["name"] == "test_field"

    @patch("devboard.api.routers.configurations.config_service.get_config_details")
    def test_get_configuration_detail_not_found(self, mock_get_details, client):
        """Test getting details for non-existent configuration."""
        mock_response = {
            "key": "nonexistent.key",
            "fields": [],
            "validation_status": "unconfigured",
            "validation_errors": ["No schema registered for key: nonexistent.key"],
        }
        mock_get_details.return_value = type("MockResponse", (), mock_response)()

        response = client.get("/api/configurations/nonexistent.key/detail")
        assert response.status_code == 404

    @patch("devboard.api.routers.configurations.config_service.update_configuration")
    def test_update_configuration_success(self, mock_update, client):
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
        mock_update.return_value = type("MockResponse", (), mock_response)()

        config_data = {"test_field": "new_value", "another_field": None}
        response = client.patch("/api/configurations/test.config.key", json=config_data)

        assert response.status_code == 200
        mock_update.assert_called_once_with("test.config.key", config_data)

    @patch("devboard.api.routers.configurations.config_service.update_configuration")
    def test_update_configuration_schema_not_found(self, mock_update, client):
        """Test updating configuration with non-existent schema."""
        mock_update.side_effect = ValueError("No schema registered for key: invalid.key")

        response = client.patch("/api/configurations/invalid.key", json={"field": "value"})
        assert response.status_code == 404
        assert "No schema registered" in response.json()["detail"]

    @patch("devboard.api.routers.configurations.config_service.delete_config")
    def test_delete_configuration_success(self, mock_delete, client):
        """Test deleting a configuration."""
        mock_delete.return_value = None  # delete_config doesn't return anything on success

        response = client.delete("/api/configurations/test.config.key")
        assert response.status_code == 200
        assert response.json()["message"] == "Configuration deleted successfully"
        mock_delete.assert_called_once_with("test.config.key")

    @patch("devboard.api.routers.configurations.config_service.delete_config")
    def test_delete_configuration_not_found(self, mock_delete, client):
        """Test deleting a non-existent configuration."""
        mock_delete.side_effect = Exception("Not found")

        response = client.delete("/api/configurations/nonexistent.key")
        assert response.status_code == 404
        assert response.json()["detail"] == "Configuration not found"
