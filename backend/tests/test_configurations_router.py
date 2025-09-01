"""Tests for configurations router."""

import pytest
from fastapi.testclient import TestClient

from devboard.db.models import Configuration, ContextProviderLink
from devboard.main import app
from devboard.repositories.configuration import ConfigurationRepository
from devboard.repositories.context_provider_link import ContextProviderLinkRepository


@pytest.fixture
def client(db_session):
    """FastAPI test client with database setup."""
    from devboard.db.database import get_db

    def override_get_db():
        return db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_config_data():
    """Sample configuration data for testing."""
    return {"key": "test.config.key", "value_json": '{"test": "value"}'}


@pytest.fixture
def test_link_data():
    """Sample context provider link data for testing."""
    return {
        "provider_name": "github",
        "parent_id": 1,
        "parent_type": "project",
        "resource_uri": "https://github.com/owner/repo",
        "description": "Test GitHub repository",
    }


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


class TestContextProviderLinksRouter:
    """Test context provider links router endpoints."""

    def test_list_provider_links_success(self, client, db_session, test_link_data):
        """Test listing provider links with valid parameters."""
        # Create test link
        link_repo = ContextProviderLinkRepository(db_session)
        link = ContextProviderLink(**test_link_data)
        link_repo.create(link)
        db_session.commit()

        response = client.get("/api/configurations/provider-links/?parent_type=project&parent_id=1")
        assert response.status_code == 200

        links = response.json()
        assert len(links) == 1
        assert links[0]["resource_uri"] == test_link_data["resource_uri"]

    def test_list_provider_links_missing_params(self, client):
        """Test listing provider links without required parameters."""
        response = client.get("/api/configurations/provider-links/")
        assert response.status_code == 400
        assert "Both parent_type and parent_id are required" in response.json()["detail"]

    def test_create_provider_link(self, client, test_link_data):
        """Test creating a new provider link."""
        response = client.post("/api/configurations/provider-links/", json=test_link_data)
        assert response.status_code == 200

        link_data = response.json()
        assert link_data["resource_uri"] == test_link_data["resource_uri"]
        assert link_data["parent_id"] == test_link_data["parent_id"]
        assert link_data["parent_type"] == test_link_data["parent_type"]
        assert link_data["provider_name"] == test_link_data["provider_name"]
        assert "id" in link_data

    def test_delete_provider_link_success(self, client, db_session, test_link_data):
        """Test deleting a provider link."""
        # Create test link
        link_repo = ContextProviderLinkRepository(db_session)
        link = ContextProviderLink(**test_link_data)
        created_link = link_repo.create(link)
        db_session.commit()

        response = client.delete(f"/api/configurations/provider-links/{created_link.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Context provider link deleted successfully"
