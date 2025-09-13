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
def mock_db_session():
    """Mock database session factory."""
    session = MagicMock()
    session_factory = MagicMock(return_value=session.__enter__.return_value)
    session.__enter__.return_value = session
    session.__exit__.return_value = None
    return session_factory, session


class TestConfigService:
    """Test ConfigService functionality."""

    def test_init_with_custom_env_vars(self, mock_db_session, mock_registry):
        """Test ConfigService initialization with custom environment variables."""
        session_factory, _ = mock_db_session
        custom_env = {"TEST_API_TOKEN": "custom_token", "OTHER_VAR": "value"}

        service = ConfigService(
            db_session_factory=session_factory,
            config_registry=mock_registry,
            env_vars=custom_env,
        )

        assert service.env_vars == custom_env
        assert service.env_vars["TEST_API_TOKEN"] == "custom_token"

    def test_init_with_default_env_vars(self, mock_db_session, mock_registry):
        """Test ConfigService initialization with default environment variables."""
        session_factory, _ = mock_db_session

        with patch.dict("os.environ", {"PATH": "/usr/bin", "HOME": "/home/user"}):
            service = ConfigService(
                db_session_factory=session_factory, config_registry=mock_registry
            )

            assert "PATH" in service.env_vars
            assert service.env_vars["PATH"] == "/usr/bin"

    def test_get_config_details_env_value_only(self, mock_db_session, mock_registry):
        """Test get_config_details when value comes from environment variable only."""
        session_factory, session = mock_db_session
        custom_env = {"TEST_API_TOKEN": "env_token_value"}

        # Mock repository to return no database data
        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
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

    def test_get_config_details_db_override(self, mock_db_session, mock_registry):
        """Test get_config_details when database overrides environment variable."""
        session_factory, session = mock_db_session
        custom_env = {"TEST_API_TOKEN": "env_token_value"}

        # Mock repository to return database data
        mock_config = Configuration(
            key="test.simple", value_json=json.dumps({"api_token": "db_override_value"})
        )
        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = mock_config

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
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

    def test_get_config_details_default_value(self, mock_db_session, mock_registry):
        """Test get_config_details when using default values."""
        session_factory, session = mock_db_session
        custom_env = {"TEST_API_TOKEN": "token"}  # No env var for max_retries

        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )

            result = service.get_config_details(SimpleTestConfig)

            # Check max_retries field uses default
            max_retries_field = next(
                f for f in result.fields if f.name == "max_retries"
            )
            assert max_retries_field.env_value is None
            assert max_retries_field.db_value is None
            assert max_retries_field.default_value == 3
            assert not max_retries_field.is_overridden
            assert max_retries_field.effective_value == 3

    def test_get_config_details_secret_detection(self, mock_db_session, mock_registry):
        """Test that secret fields are properly detected."""
        session_factory, session = mock_db_session
        custom_env = {
            "COMPLEX_DATABASE_URL": "postgres://localhost",
            "COMPLEX_SECRET_KEY": "secret123",
        }

        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )

            result = service.get_config_details(ComplexTestConfig)

            # Check secret fields are marked
            secret_key_field = next(f for f in result.fields if f.name == "secret_key")
            assert secret_key_field.is_secret

            api_key_field = next(f for f in result.fields if f.name == "api_key")
            assert api_key_field.is_secret

            # Non-secret fields
            database_url_field = next(
                f for f in result.fields if f.name == "database_url"
            )
            assert not database_url_field.is_secret

    def test_get_config_details_validation_errors(self, mock_db_session, mock_registry):
        """Test get_config_details with validation errors."""
        session_factory, session = mock_db_session
        custom_env = {}  # Missing required fields

        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )

            result = service.get_config_details(SimpleTestConfig)

            assert result.validation_status == "invalid"
            assert result.validation_errors is not None
            assert len(result.validation_errors) > 0
            assert "api_token" in result.validation_errors[0]

    def test_update_configuration_add_override(self, mock_db_session, mock_registry):
        """Test update_configuration adding database override."""
        session_factory, session = mock_db_session
        custom_env = {"TEST_API_TOKEN": "env_token"}

        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
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
            mock_repo.create.assert_called_once()
            created_config = mock_repo.create.call_args[0][0]
            saved_data = json.loads(created_config.value_json)
            assert saved_data["api_token"] == "new_override"
            assert saved_data["webhook_url"] == "https://example.com/webhook"
            assert saved_data["max_retries"] == 5

    def test_update_configuration_clear_override(self, mock_db_session, mock_registry):
        """Test update_configuration clearing database override with None."""
        session_factory, session = mock_db_session
        custom_env = {"TEST_API_TOKEN": "env_token"}

        # Existing database data
        existing_config = Configuration(
            key="test.simple",
            value_json=json.dumps(
                {
                    "api_token": "db_override",
                    "webhook_url": "https://old.com",
                    "max_retries": 10,
                }
            ),
        )
        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = existing_config

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )

            # Clear api_token override, keep webhook_url, clear max_retries
            config_data = {
                "api_token": None,  # Clear override
                "webhook_url": "https://new.com",  # Keep override
                "max_retries": None,  # Clear override
            }

            result = service.update_configuration("test.simple", config_data)

            # Verify update was called with correct data
            mock_repo.update.assert_called_once()
            saved_data = json.loads(existing_config.value_json)
            assert "api_token" not in saved_data  # Cleared
            assert saved_data["webhook_url"] == "https://new.com"  # Updated
            assert "max_retries" not in saved_data  # Cleared

    def test_update_configuration_schema_not_found(self, mock_db_session):
        """Test update_configuration with non-existent schema."""
        session_factory, session = mock_db_session
        empty_registry = MagicMock()
        empty_registry.get.return_value = None

        service = ConfigService(
            db_session_factory=session_factory,
            config_registry=empty_registry,
            env_vars={},
        )

        with pytest.raises(ValueError, match="No schema registered"):
            service.update_configuration("nonexistent.key", {"field": "value"})

    def test_list_configs_no_prefix(self, mock_db_session, mock_registry):
        """Test list_configs without prefix filter."""
        session_factory, _ = mock_db_session

        service = ConfigService(
            db_session_factory=session_factory,
            config_registry=mock_registry,
            env_vars={},
        )

        configs = service.list_configs()

        assert len(configs) == 2
        assert "test.simple" in configs
        assert "test.complex" in configs

    def test_list_configs_with_prefix(self, mock_db_session, mock_registry):
        """Test list_configs with prefix filter."""
        session_factory, _ = mock_db_session
        mock_registry.list_keys.return_value = [
            "test.simple",
            "test.complex",
            "other.config",
        ]

        service = ConfigService(
            db_session_factory=session_factory,
            config_registry=mock_registry,
            env_vars={},
        )

        configs = service.list_configs(prefix="test.")

        assert len(configs) == 2
        assert "test.simple" in configs
        assert "test.complex" in configs
        assert "other.config" not in configs

    def test_delete_config_success(self, mock_db_session, mock_registry):
        """Test successful configuration deletion."""
        session_factory, session = mock_db_session

        mock_repo = MagicMock()
        mock_repo.delete_by_key.return_value = True

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars={},
            )

            service.delete_config("test.simple")

            mock_repo.delete_by_key.assert_called_once_with("test.simple")
            # Commit is called on the session returned by __enter__
            session_factory.return_value.__enter__.return_value.commit.assert_called_once()

    def test_validate_config_success(self, mock_db_session, mock_registry):
        """Test successful configuration validation."""
        session_factory, session = mock_db_session
        custom_env = {"TEST_API_TOKEN": "valid_token"}

        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )

            result = service.validate_config(SimpleTestConfig)

            assert result.success
            assert result.config is not None
            assert result.config.api_token == "valid_token"
            assert result.errors == []

    def test_validate_config_missing_required(self, mock_db_session, mock_registry):
        """Test configuration validation with missing required fields."""
        session_factory, session = mock_db_session
        custom_env = {}  # Missing TEST_API_TOKEN

        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )

            result = service.validate_config(SimpleTestConfig)

            assert not result.success
            assert result.config is None
            assert result.errors is not None
            assert any("api_token" in error for error in result.errors)

    def test_get_config_success(self, mock_db_session, mock_registry):
        """Test get_config returns config when valid."""
        session_factory, session = mock_db_session
        custom_env = {"TEST_API_TOKEN": "valid_token"}

        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )

            config = service.get_config(SimpleTestConfig)

            assert config is not None
            assert config.api_token == "valid_token"

    def test_get_config_validation_failure(self, mock_db_session, mock_registry):
        """Test get_config returns None when validation fails."""
        session_factory, session = mock_db_session
        custom_env = {}  # Missing required fields

        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = None

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )

            config = service.get_config(SimpleTestConfig)

            assert config is None

    def test_priority_hierarchy(self, mock_db_session, mock_registry):
        """Test that priority hierarchy works: db > env > default."""
        session_factory, session = mock_db_session
        custom_env = {
            "TEST_API_TOKEN": "env_token",
            "TEST_MAX_RETRIES": "7",  # Env value for max_retries
        }

        # Database has api_token and webhook_url
        mock_config = Configuration(
            key="test.simple",
            value_json=json.dumps(
                {"api_token": "db_token", "webhook_url": "https://db.com"}
            ),
        )
        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = mock_config

        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )

            result = service.get_config_details(SimpleTestConfig)

            # api_token: db overrides env
            api_token_field = next(f for f in result.fields if f.name == "api_token")
            assert api_token_field.effective_value == "db_token"

            # webhook_url: db value (no env)
            webhook_field = next(f for f in result.fields if f.name == "webhook_url")
            assert webhook_field.effective_value == "https://db.com"

            # max_retries: env value (no db)
            max_retries_field = next(
                f for f in result.fields if f.name == "max_retries"
            )
            assert max_retries_field.env_value == "7"
            assert max_retries_field.effective_value == "7"

    def test_config_without_env_prefix(self, mock_db_session, mock_registry):
        """Test configuration without env_prefix - should only use DB values and defaults."""
        session_factory, session = mock_db_session
        
        # Set up environment variables that would match field names
        # These should NOT be picked up since there's no env_prefix
        custom_env = {
            "SERVICE_URL": "env_service_url",
            "TIMEOUT": "60",
            "ENABLE_CACHE": "false",
        }
        
        # Database has service_url override
        mock_config = Configuration(
            key="test.no_env_prefix",
            value_json=json.dumps({"service_url": "https://db-service.com"}),
        )
        mock_repo = MagicMock()
        mock_repo.get_by_key.return_value = mock_config
        
        with patch(
            "devboard.services.config_service.ConfigurationRepository",
            return_value=mock_repo,
        ):
            service = ConfigService(
                db_session_factory=session_factory,
                config_registry=mock_registry,
                env_vars=custom_env,
            )
            
            result = service.get_config_details(NoEnvPrefixConfig)
            
            # service_url: should use DB value, not env var
            service_url_field = next(f for f in result.fields if f.name == "service_url")
            assert service_url_field.env_value is None  # No env var should be read
            assert service_url_field.db_value == "https://db-service.com"
            assert service_url_field.effective_value == "https://db-service.com"
            assert service_url_field.env_var_name is None
            
            # timeout: should use default value, not env var
            timeout_field = next(f for f in result.fields if f.name == "timeout")
            assert timeout_field.env_value is None  # No env var should be read
            assert timeout_field.db_value is None
            assert timeout_field.default_value == 30
            assert timeout_field.effective_value == 30
            assert timeout_field.env_var_name is None
            
            # enable_cache: should use default value, not env var
            enable_cache_field = next(f for f in result.fields if f.name == "enable_cache")
            assert enable_cache_field.env_value is None  # No env var should be read
            assert enable_cache_field.db_value is None
            assert enable_cache_field.default_value is True
            assert enable_cache_field.effective_value is True
            assert enable_cache_field.env_var_name is None
