"""Tests for configurations router."""

import pytest

from devboard.db.models import Configuration
from devboard.db.repositories import ConfigurationRepository


@pytest.fixture
def test_config_data():
    """Sample configuration data for testing."""
    return {"key": "test.config.key", "value_json": '{"test": "value"}'}


class TestConfigurationsRouter:
    """Test configurations router endpoints."""

    def test_list_configurations_empty(self, client):
        """Test listing configurations when none exist."""
        response = client.get("/api/configurations/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_configurations_with_data(self, client, db_session, test_config_data):
        """Test listing configurations with existing data."""
        # Create test configuration
        config_repo = ConfigurationRepository(db_session)
        config = Configuration(**test_config_data)
        config_repo.create(config)
        db_session.commit()

        response = client.get("/api/configurations/")
        assert response.status_code == 200
        configs = response.json()
        assert len(configs) == 1
        assert configs[0]["key"] == test_config_data["key"]

    def test_get_configuration_success(self, client, db_session, test_config_data):
        """Test getting a specific configuration."""
        # Create test configuration
        config_repo = ConfigurationRepository(db_session)
        config = Configuration(**test_config_data)
        config_repo.create(config)
        db_session.commit()

        response = client.get(f"/api/configurations/{test_config_data['key']}")
        assert response.status_code == 200

        config_data = response.json()
        assert config_data["key"] == test_config_data["key"]
        assert config_data["value_json"] == test_config_data["value_json"]

    def test_get_configuration_not_found(self, client):
        """Test getting a non-existent configuration."""
        response = client.get("/api/configurations/nonexistent.key")
        assert response.status_code == 404
        assert response.json()["detail"] == "Configuration not found"

    def test_create_configuration(self, client, test_config_data):
        """Test creating a new configuration."""
        response = client.post("/api/configurations/", json=test_config_data)
        assert response.status_code == 200

        config_data = response.json()
        assert config_data["key"] == test_config_data["key"]
        assert config_data["value_json"] == test_config_data["value_json"]

    def test_delete_configuration_success(self, client, db_session, test_config_data):
        """Test deleting a configuration."""
        # Create test configuration
        config_repo = ConfigurationRepository(db_session)
        config = Configuration(**test_config_data)
        config_repo.create(config)
        db_session.commit()

        response = client.delete(f"/api/configurations/{test_config_data['key']}")
        assert response.status_code == 200
        assert response.json()["message"] == "Configuration deleted successfully"
