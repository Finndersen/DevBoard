"""Tests for ConfigService."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import Field

from devboard.config.base import BaseConfig
from devboard.db.models import Configuration
from devboard.services.config_service import ConfigService


# Test configuration schemas - avoid Test prefix to prevent pytest warnings
class SimpleTestConfig(BaseConfig):
    """Simple test configuration."""

    api_token: str = Field(description="API token for testing")
    webhook_url: str | None = Field(default=None, description="Webhook URL")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    env_prefix = "TEST_"
    config_key = "test.simple"


class ComplexTestConfig(BaseConfig):
    """Complex test configuration with secrets."""

    database_url: str = Field(description="Database connection URL")
    secret_key: str = Field(description="Secret encryption key")
    api_key: str | None = Field(default=None, description="Optional API key")
    debug_mode: bool = Field(default=False, description="Enable debug mode")

    env_prefix = "COMPLEX_"
    config_key = "test.complex"


class NoEnvPrefixConfig(BaseConfig):
    """Test configuration without env_prefix."""

    service_url: str = Field(description="Service endpoint URL")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    enable_cache: bool = Field(default=True, description="Enable caching")

    # No env_prefix defined
    config_key = "test.no_env_prefix"


@pytest.fixture
def mock_registry():
    """Mock configuration registry."""
    registry = MagicMock()
    registry.get.side_effect = lambda key: {
        "test.simple": SimpleTestConfig,
        "test.complex": ComplexTestConfig,
    }.get(key)
    registry.list_keys.return_value = ["test.simple", "test.complex"]
    return registry


@pytest.fixture
def mock_config_repository():
    """Mock configuration repository."""
    return MagicMock()


class TestConfigService:
    """Test ConfigService functionality."""

    def test_init_with_custom_env_vars(self, mock_config_repository, mock_registry):
        """Test ConfigService initialization with custom environment variables."""
        custom_env = {"TEST_API_TOKEN": "custom_token", "OTHER_VAR": "value"}

        service = ConfigService(
            configuration_repository=mock_config_repository,
            config_registry=mock_registry,
            env_vars=custom_env,
        )

        assert service.env_vars == custom_env
        assert service.env_vars["TEST_API_TOKEN"] == "custom_token"

    def test_init_with_default_env_vars(self, mock_config_repository, mock_registry):
        """Test ConfigService initialization with default environment variables."""
        with patch.dict("os.environ", {"PATH": "/usr/bin", "HOME": "/home/user"}):
            service = ConfigService(configuration_repository=mock_config_repository, config_registry=mock_registry)

            assert "PATH" in service.env_vars
            assert service.env_vars["PATH"] == "/usr/bin"

    def test_get_config_details_env_value_only(self, mock_config_repository, mock_registry):
        """Test get_config_details when value comes from environment variable only."""
        custom_env = {"TEST_API_TOKEN": "env_token_value"}

        # Mock repository to return no database data
        mock_config_repository.get_by_key.return_value = None

        service = ConfigService(
            configuration_repository=mock_config_repository,
            config_registry=mock_registry,
            env_vars=custom_env,
        )

        result = service.get_config_details(SimpleTestConfig)

        assert result.key == "test.simple"
        assert len(result.fields) == 3

        # Check api_token field
        api_token_field = next(f for f in result.fields if f.name == "api_token")
        assert api_token_field.env_value == "env_token_value"
        assert api_token_field.db_value is None
        assert api_token_field.default_value is None
        assert not api_token_field.is_overridden
        assert api_token_field.effective_value == "env_token_value"

    def test_get_config_details_db_override(self, mock_config_repository, mock_registry):
        """Test get_config_details when database overrides environment variable."""
        custom_env = {"TEST_API_TOKEN": "env_token_value"}

        # Mock repository to return database data
        mock_config = Configuration(key="test.simple", value_json=json.dumps({"api_token": "db_override_value"}))
        mock_config_repository.get_by_key.return_value = mock_config

        service = ConfigService(
            configuration_repository=mock_config_repository,
            config_registry=mock_registry,
            env_vars=custom_env,
        )

        result = service.get_config_details(SimpleTestConfig)

        # Check api_token field has both env and db values
        api_token_field = next(f for f in result.fields if f.name == "api_token")
        assert api_token_field.env_value == "env_token_value"
        assert api_token_field.db_value == "db_override_value"
        assert api_token_field.is_overridden
        assert api_token_field.effective_value == "db_override_value"

    def test_validate_config_success(self, mock_config_repository, mock_registry):
        """Test successful configuration validation."""
        custom_env = {"TEST_API_TOKEN": "valid_token"}

        mock_config_repository.get_by_key.return_value = None

        service = ConfigService(
            configuration_repository=mock_config_repository,
            config_registry=mock_registry,
            env_vars=custom_env,
        )

        result = service.validate_config(SimpleTestConfig)

        assert result.success
        assert result.config is not None
        assert result.config.api_token == "valid_token"
        assert result.errors == []

    def test_get_config_success(self, mock_config_repository, mock_registry):
        """Test get_config returns config when valid."""
        custom_env = {"TEST_API_TOKEN": "valid_token"}

        mock_config_repository.get_by_key.return_value = None

        service = ConfigService(
            configuration_repository=mock_config_repository,
            config_registry=mock_registry,
            env_vars=custom_env,
        )

        config = service.get_config(SimpleTestConfig)

        assert config is not None
        assert config.api_token == "valid_token"

    def test_update_configuration_add_override(self, mock_config_repository, mock_registry):
        """Test update_configuration adding database override."""
        custom_env = {"TEST_API_TOKEN": "env_token"}

        mock_config_repository.get_by_key.return_value = None

        service = ConfigService(
            configuration_repository=mock_config_repository,
            config_registry=mock_registry,
            env_vars=custom_env,
        )

        # Update with override values
        config_data = {
            "api_token": "new_override",
            "webhook_url": "https://example.com/webhook",
            "max_retries": 5,
        }

        result = service.update_configuration("test.simple", config_data)

        # Verify create was called with correct data
        mock_config_repository.create.assert_called_once()
        created_config = mock_config_repository.create.call_args[0][0]
        saved_data = json.loads(created_config.value_json)
        assert saved_data["api_token"] == "new_override"
        assert saved_data["webhook_url"] == "https://example.com/webhook"
        assert saved_data["max_retries"] == 5

    def test_delete_config_success(self, mock_config_repository, mock_registry):
        """Test successful configuration deletion."""
        service = ConfigService(
            configuration_repository=mock_config_repository,
            config_registry=mock_registry,
            env_vars={},
        )

        service.delete_config("test.simple")

        mock_config_repository.delete_by_key.assert_called_once_with("test.simple")

    def test_list_configs_no_prefix(self, mock_config_repository, mock_registry):
        """Test list_configs without prefix filter."""
        service = ConfigService(
            configuration_repository=mock_config_repository,
            config_registry=mock_registry,
            env_vars={},
        )

        configs = service.list_configs()

        assert len(configs) == 2
        assert "test.simple" in configs
        assert "test.complex" in configs
