"""Tests for configurations router."""

from unittest.mock import Mock

import pytest

from devboard.api.dependencies.services import get_config_service
from devboard.api.main import app
from devboard.services.config_service import ConfigService, ConfigurationDetail, ConfigurationFieldInfo


@pytest.fixture
def mock_config_service():
    """Mock ConfigService for testing."""
    return Mock(spec=ConfigService)


@pytest.fixture
def client_with_mock_config_service(client, mock_config_service):
    """Client with mocked config service."""
    app.dependency_overrides[get_config_service] = lambda: mock_config_service
    yield client
    # Clean up after test
    if get_config_service in app.dependency_overrides:
        del app.dependency_overrides[get_config_service]


@pytest.fixture
def test_config_data():
    """Sample configuration data for testing."""
    return {"api_key": "test-api-key-123", "base_url": "https://api.test.com"}


@pytest.fixture
def invalid_config_data():
    """Invalid configuration data for testing."""
    return {"invalid_field": "should_not_exist"}


class TestConfigurationsRouter:
    """Test configurations router endpoints."""

    def test_list_configurations_requires_prefix(self, client_with_mock_config_service, mock_config_service):
        """Test that listing configurations requires a prefix parameter."""
        # Test without prefix - should fail
        response = client_with_mock_config_service.get("/api/configurations/")
        assert response.status_code == 422  # Validation error for missing required parameter

    def test_list_configurations_with_prefix_returns_detail_responses(
        self, client_with_mock_config_service, mock_config_service
    ):
        """Test that listing configurations returns ConfigurationDetailResponse objects."""
        # Setup mock response with schemas
        mock_config_service.list_configs.return_value = [
            "llm.openai.main",
            "llm.anthropic.main",
        ]

        # Mock the get_config_details_by_key calls
        mock_config_service.get_config_details_by_key.side_effect = [
            ConfigurationDetail(
                key="llm.openai.main",
                is_valid=True,
                validation_errors=[],
                fields=[ConfigurationFieldInfo(name="api_key", type="str", required=True)],
            ),
            ConfigurationDetail(
                key="llm.anthropic.main",
                is_valid=False,
                validation_errors=["Missing API key"],
                fields=[ConfigurationFieldInfo(name="api_key", type="str", required=True)],
            ),
        ]

        response = client_with_mock_config_service.get("/api/configurations/?prefix=llm")
        assert response.status_code == 200
        configs = response.json()

        # Should return ConfigurationDetailResponse objects
        assert len(configs) == 2
        assert configs[0]["key"] == "llm.openai.main"
        assert configs[0]["is_valid"] is True
        assert configs[1]["key"] == "llm.anthropic.main"
        assert configs[1]["is_valid"] is False

        # Verify service was called with prefix
        mock_config_service.list_configs.assert_called_once_with(prefix="llm")

    def test_list_configurations_filters_none_responses(self, client_with_mock_config_service, mock_config_service):
        """Test that listing configurations filters out None responses from get_config_details_by_key."""
        # Setup mock response with schemas
        mock_config_service.list_configs.return_value = [
            "llm.openai.main",
            "invalid.key",
            "llm.anthropic.main",
        ]

        # Mock get_config_details_by_key to return None for invalid key
        mock_config_service.get_config_details_by_key.side_effect = [
            ConfigurationDetail(key="llm.openai.main", is_valid=True, validation_errors=[], fields=[]),
            None,  # This should be filtered out
            ConfigurationDetail(
                key="llm.anthropic.main", is_valid=False, validation_errors=["Missing API key"], fields=[]
            ),
        ]

        response = client_with_mock_config_service.get("/api/configurations/?prefix=llm")
        assert response.status_code == 200
        configs = response.json()

        # Should only return non-None responses
        assert len(configs) == 2
        assert configs[0]["key"] == "llm.openai.main"
        assert configs[1]["key"] == "llm.anthropic.main"

    def test_get_configuration_detail_success(self, client_with_mock_config_service, mock_config_service):
        """Test getting detailed configuration information for valid config."""
        # Setup mock response
        mock_config_service.get_config_details_by_key.return_value = ConfigurationDetail(
            key="llm.openai.main",
            is_valid=True,
            validation_errors=[],
            fields=[
                ConfigurationFieldInfo(
                    name="api_key",
                    type="str",
                    required=True,
                    default_value=None,
                    db_value="test-openai-key",
                    env_value=None,
                    effective_value="test-openai-key",
                    source="database",
                ),
                ConfigurationFieldInfo(
                    name="base_url",
                    type="str",
                    required=False,
                    default_value="https://api.openai.com/v1",
                    db_value="https://api.openai.com/v1",
                    env_value=None,
                    effective_value="https://api.openai.com/v1",
                    source="database",
                ),
            ],
        )

        response = client_with_mock_config_service.get("/api/configurations/llm.openai.main/detail")
        assert response.status_code == 200

        config_data = response.json()
        assert config_data["key"] == "llm.openai.main"
        assert config_data["is_valid"] is True
        assert config_data["validation_errors"] == []
        assert len(config_data["fields"]) == 2

        # Check specific field details
        field_names = [field["name"] for field in config_data["fields"]]
        assert "api_key" in field_names
        assert "base_url" in field_names

        # Verify service was called correctly
        mock_config_service.get_config_details_by_key.assert_called_once_with("llm.openai.main")

    def test_get_configuration_detail_missing_required_field(
        self, client_with_mock_config_service, mock_config_service
    ):
        """Test getting configuration details when required field is missing."""
        # Setup mock response with validation errors
        mock_config_service.get_config_details_by_key.return_value = ConfigurationDetail(
            key="llm.openai.main",
            is_valid=False,
            validation_errors=["Field 'api_key' is required but not set"],
            fields=[
                ConfigurationFieldInfo(
                    name="api_key",
                    type="str",
                    required=True,
                    default_value=None,
                    db_value=None,
                    env_value=None,
                    effective_value=None,
                    source="none",
                ),
                ConfigurationFieldInfo(
                    name="base_url",
                    type="str",
                    required=False,
                    default_value="https://api.openai.com/v1",
                    db_value="https://api.openai.com/v1",
                    env_value=None,
                    effective_value="https://api.openai.com/v1",
                    source="database",
                ),
            ],
        )

        response = client_with_mock_config_service.get("/api/configurations/llm.openai.main/detail")
        assert response.status_code == 200

        config_data = response.json()
        assert config_data["key"] == "llm.openai.main"
        assert config_data["is_valid"] is False
        assert len(config_data["validation_errors"]) > 0
        # Should mention missing api_key
        assert any("api_key" in error for error in config_data["validation_errors"])

        # Verify service was called correctly
        mock_config_service.get_config_details_by_key.assert_called_once_with("llm.openai.main")

    def test_get_configuration_detail_not_found(self, client_with_mock_config_service, mock_config_service):
        """Test getting details for non-existent configuration schema."""
        # Setup mock to return None indicating no schema exists
        mock_config_service.get_config_details_by_key.return_value = None

        response = client_with_mock_config_service.get("/api/configurations/nonexistent.key/detail")
        assert response.status_code == 404

        # Verify service was called correctly
        mock_config_service.get_config_details_by_key.assert_called_once_with("nonexistent.key")

    def test_get_configuration_detail_unconfigured_schema(self, client_with_mock_config_service, mock_config_service):
        """Test getting details for valid schema with no database configuration."""
        # Setup mock response for unconfigured but valid schema
        mock_config_service.get_config_details_by_key.return_value = ConfigurationDetail(
            key="llm.openai.main",
            is_valid=False,
            validation_errors=["Field 'api_key' is required but not set"],
            fields=[
                ConfigurationFieldInfo(
                    name="api_key",
                    type="str",
                    required=True,
                    default_value=None,
                    db_value=None,
                    env_value=None,
                    effective_value=None,
                    source="none",
                ),
                ConfigurationFieldInfo(
                    name="base_url",
                    type="str",
                    required=False,
                    default_value="https://api.openai.com/v1",
                    db_value=None,
                    env_value=None,
                    effective_value="https://api.openai.com/v1",
                    source="default",
                ),
            ],
        )

        response = client_with_mock_config_service.get("/api/configurations/llm.openai.main/detail")
        assert response.status_code == 200

        config_data = response.json()
        assert config_data["key"] == "llm.openai.main"
        # Without api_key (required field), it should be invalid
        assert config_data["is_valid"] is False
        assert len(config_data["validation_errors"]) > 0

        # Verify service was called correctly
        mock_config_service.get_config_details_by_key.assert_called_once_with("llm.openai.main")

    def test_update_configuration_success(self, client_with_mock_config_service, mock_config_service, test_config_data):
        """Test updating configuration with valid data."""
        update_data = {"api_key": "updated-api-key-456", "base_url": "https://custom.openai.com/v1"}

        # Setup mock response for successful update
        mock_config_service.update_configuration.return_value = ConfigurationDetail(
            key="llm.openai.main",
            is_valid=True,
            validation_errors=[],
            fields=[
                ConfigurationFieldInfo(
                    name="api_key",
                    type="str",
                    required=True,
                    default_value=None,
                    db_value="updated-api-key-456",
                    env_value=None,
                    effective_value="updated-api-key-456",
                    source="database",
                ),
                ConfigurationFieldInfo(
                    name="base_url",
                    type="str",
                    required=False,
                    default_value="https://api.openai.com/v1",
                    db_value="https://custom.openai.com/v1",
                    env_value=None,
                    effective_value="https://custom.openai.com/v1",
                    source="database",
                ),
            ],
        )

        response = client_with_mock_config_service.patch("/api/configurations/llm.openai.main", json=update_data)
        assert response.status_code == 200

        config_data = response.json()
        assert config_data["key"] == "llm.openai.main"
        assert config_data["is_valid"] is True
        assert config_data["validation_errors"] == []

        # Verify the values were updated
        api_key_field = next(field for field in config_data["fields"] if field["name"] == "api_key")
        assert api_key_field["db_value"] == "updated-api-key-456"

        # Verify service was called correctly
        mock_config_service.update_configuration.assert_called_once_with("llm.openai.main", update_data)

    def test_update_configuration_partial_update(self, client_with_mock_config_service, mock_config_service):
        """Test partial update of configuration (only update some fields)."""
        # Update only api_key
        update_data = {"api_key": "new-key"}

        # Setup mock response for partial update
        mock_config_service.update_configuration.return_value = ConfigurationDetail(
            key="llm.openai.main",
            is_valid=True,
            validation_errors=[],
            fields=[
                ConfigurationFieldInfo(
                    name="api_key",
                    type="str",
                    required=True,
                    default_value=None,
                    db_value="new-key",
                    env_value=None,
                    effective_value="new-key",
                    source="database",
                ),
                ConfigurationFieldInfo(
                    name="base_url",
                    type="str",
                    required=False,
                    default_value="https://api.openai.com/v1",
                    db_value="https://api.openai.com/v1",
                    env_value=None,
                    effective_value="https://api.openai.com/v1",
                    source="database",
                ),
            ],
        )

        response = client_with_mock_config_service.patch("/api/configurations/llm.openai.main", json=update_data)
        assert response.status_code == 200

        config_data = response.json()
        assert config_data["is_valid"] is True

        # Verify api_key was updated but base_url remains
        api_key_field = next(field for field in config_data["fields"] if field["name"] == "api_key")
        base_url_field = next(field for field in config_data["fields"] if field["name"] == "base_url")
        assert api_key_field["db_value"] == "new-key"
        assert base_url_field["db_value"] == "https://api.openai.com/v1"

        # Verify service was called correctly
        mock_config_service.update_configuration.assert_called_once_with("llm.openai.main", update_data)

    def test_update_configuration_clear_field_with_none(self, client_with_mock_config_service, mock_config_service):
        """Test clearing a database field by setting it to None."""
        # Clear organization_id by setting to None
        update_data = {"organization_id": None}

        # Setup mock response for field clearing
        mock_config_service.update_configuration.return_value = ConfigurationDetail(
            key="llm.openai.main",
            is_valid=True,
            validation_errors=[],
            fields=[
                ConfigurationFieldInfo(
                    name="api_key",
                    type="str",
                    required=True,
                    default_value=None,
                    db_value="test-key",
                    env_value=None,
                    effective_value="test-key",
                    source="database",
                ),
                ConfigurationFieldInfo(
                    name="organization_id",
                    type="str",
                    required=False,
                    default_value=None,
                    db_value=None,
                    env_value=None,
                    effective_value=None,
                    source="none",
                ),
            ],
        )

        response = client_with_mock_config_service.patch("/api/configurations/llm.openai.main", json=update_data)
        assert response.status_code == 200

        config_data = response.json()
        org_field = next(field for field in config_data["fields"] if field["name"] == "organization_id")
        assert org_field["db_value"] is None

        # Verify service was called correctly
        mock_config_service.update_configuration.assert_called_once_with("llm.openai.main", update_data)

    def test_update_configuration_schema_not_found(self, client_with_mock_config_service, mock_config_service):
        """Test updating configuration with non-existent schema."""
        # Setup mock to raise ValueError for non-existent schema
        mock_config_service.update_configuration.side_effect = ValueError("No schema registered for key: invalid.key")

        response = client_with_mock_config_service.patch("/api/configurations/invalid.key", json={"field": "value"})
        assert response.status_code == 404
        assert "No schema registered" in response.json()["detail"]

        # Verify service was called correctly
        mock_config_service.update_configuration.assert_called_once_with("invalid.key", {"field": "value"})

    def test_update_configuration_invalid_data(
        self, client_with_mock_config_service, mock_config_service, invalid_config_data
    ):
        """Test updating configuration with invalid field data."""
        # Setup mock to raise ValueError for validation error
        mock_config_service.update_configuration.side_effect = ValueError("Invalid field: invalid_field")

        response = client_with_mock_config_service.patch(
            "/api/configurations/llm.openai.main", json=invalid_config_data
        )
        assert response.status_code == 400
        error_detail = response.json()["detail"]
        assert "Invalid field" in error_detail

        # Verify service was called correctly
        mock_config_service.update_configuration.assert_called_once_with("llm.openai.main", invalid_config_data)

    def test_delete_configuration_success(self, client_with_mock_config_service, mock_config_service):
        """Test deleting a configuration."""
        # Setup mock for successful delete
        mock_config_service.delete_config.return_value = None

        response = client_with_mock_config_service.delete("/api/configurations/llm.openai.main")
        assert response.status_code == 200
        assert response.json()["message"] == "Configuration deleted successfully"
        assert response.json()["success"] is True

        # Verify service was called correctly
        mock_config_service.delete_config.assert_called_once_with("llm.openai.main")

    def test_delete_configuration_not_found(self, client_with_mock_config_service, mock_config_service):
        """Test deleting a non-existent configuration."""
        # Setup mock for successful delete (service doesn't raise exception for missing keys)
        mock_config_service.delete_config.return_value = None

        response = client_with_mock_config_service.delete("/api/configurations/nonexistent.key")
        # The current implementation returns 200 even for non-existent keys
        # This is because delete_config doesn't raise an exception for missing keys
        assert response.status_code == 200
        assert response.json()["message"] == "Configuration deleted successfully"
        assert response.json()["success"] is True

        # Verify service was called correctly
        mock_config_service.delete_config.assert_called_once_with("nonexistent.key")

    def test_end_to_end_configuration_flow(self, client_with_mock_config_service, mock_config_service):
        """Test complete configuration lifecycle: create, read, update, delete."""
        config_key = "llm.anthropic.main"

        # Setup mock responses for the flow
        # 1. Initially invalid configuration
        invalid_response = ConfigurationDetail(
            key=config_key,
            is_valid=False,
            validation_errors=["Field 'api_key' is required but not set"],
            fields=[
                ConfigurationFieldInfo(
                    name="api_key",
                    type="str",
                    required=True,
                    default_value=None,
                    db_value=None,
                    env_value=None,
                    effective_value=None,
                    source="none",
                )
            ],
        )

        # 2. Valid configuration after update
        valid_response = ConfigurationDetail(
            key=config_key,
            is_valid=True,
            validation_errors=[],
            fields=[
                ConfigurationFieldInfo(
                    name="api_key",
                    type="str",
                    required=True,
                    default_value=None,
                    db_value="test-anthropic-key",
                    env_value=None,
                    effective_value="test-anthropic-key",
                    source="database",
                )
            ],
        )

        # 3. Updated configuration
        updated_response = ConfigurationDetail(
            key=config_key,
            is_valid=True,
            validation_errors=[],
            fields=[
                ConfigurationFieldInfo(
                    name="api_key",
                    type="str",
                    required=True,
                    default_value=None,
                    db_value="updated-anthropic-key",
                    env_value=None,
                    effective_value="updated-anthropic-key",
                    source="database",
                ),
                ConfigurationFieldInfo(
                    name="base_url",
                    type="str",
                    required=False,
                    default_value="https://api.anthropic.com",
                    db_value="https://custom.anthropic.com",
                    env_value=None,
                    effective_value="https://custom.anthropic.com",
                    source="database",
                ),
            ],
        )

        # Configure mock responses in sequence
        mock_config_service.get_config_details_by_key.side_effect = [
            invalid_response,  # Step 1 (initial detail get)
            valid_response,  # Step 3 (list endpoint detail call)
            valid_response,  # Step 4 (read back)
            updated_response,  # Step 6 (verify update)
            invalid_response,  # Step 8 (after delete)
            invalid_response,  # Step 9 (list endpoint detail call after delete)
        ]
        mock_config_service.update_configuration.side_effect = [valid_response, updated_response]
        mock_config_service.list_configs.side_effect = [[config_key], [config_key]]  # Steps 3 and 9

        # 1. Initially should show invalid due to missing required field
        response = client_with_mock_config_service.get(f"/api/configurations/{config_key}/detail")
        assert response.status_code == 200
        assert response.json()["is_valid"] is False

        # 2. Update with valid configuration
        config_data = {"api_key": "test-anthropic-key"}
        response = client_with_mock_config_service.patch(f"/api/configurations/{config_key}", json=config_data)
        assert response.status_code == 200
        assert response.json()["is_valid"] is True

        # 3. Verify it appears in the list
        response = client_with_mock_config_service.get("/api/configurations/?prefix=llm")
        assert response.status_code == 200
        configs = response.json()
        assert len(configs) == 1
        assert configs[0]["key"] == config_key

        # 4. Verify we can read it back
        response = client_with_mock_config_service.get(f"/api/configurations/{config_key}/detail")
        assert response.status_code == 200
        config_detail = response.json()
        assert config_detail["is_valid"] is True
        api_key_field = next(field for field in config_detail["fields"] if field["name"] == "api_key")
        assert api_key_field["db_value"] == "test-anthropic-key"

        # 5. Update it
        updated_data = {"api_key": "updated-anthropic-key", "base_url": "https://custom.anthropic.com"}
        response = client_with_mock_config_service.patch(f"/api/configurations/{config_key}", json=updated_data)
        assert response.status_code == 200

        # 6. Verify the update
        response = client_with_mock_config_service.get(f"/api/configurations/{config_key}/detail")
        config_detail = response.json()
        api_key_field = next(field for field in config_detail["fields"] if field["name"] == "api_key")
        base_url_field = next(field for field in config_detail["fields"] if field["name"] == "base_url")
        assert api_key_field["db_value"] == "updated-anthropic-key"
        assert base_url_field["db_value"] == "https://custom.anthropic.com"

        # 7. Delete it
        response = client_with_mock_config_service.delete(f"/api/configurations/{config_key}")
        assert response.status_code == 200

        # 8. Verify it's deleted but schema still exists (should be invalid now)
        response = client_with_mock_config_service.get(f"/api/configurations/{config_key}/detail")
        assert response.status_code == 200
        assert response.json()["is_valid"] is False

        # 9. Should still appear in list (since it's a registered schema)
        response = client_with_mock_config_service.get("/api/configurations/?prefix=llm")
        assert response.status_code == 200
        configs = response.json()
        assert len(configs) == 1
        assert configs[0]["key"] == config_key
