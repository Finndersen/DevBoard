"""Service for managing application configuration."""

import json
import os
from typing import Any, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError, computed_field
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from devboard.config.base import BaseConfig, ConfigValidationResult
from devboard.config.registry import config_schema_registry
from devboard.core.registry import Registry
from devboard.db.models import Configuration
from devboard.db.repositories.configuration import ConfigurationRepository

T = TypeVar("T", bound="BaseConfig")


class ConfigurationNotFoundError(Exception):
    """Raised when a configuration key has no registered schema."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"No schema registered for key: {key}")


class ConfigurationFieldInfo(BaseModel):
    """Information about a single configuration field with explicit value sources."""

    name: str
    type: str  # "string", "boolean", "integer", "number"
    required: bool
    description: str | None = None
    env_value: Any | None = None  # Value from environment variable
    db_value: Any | None = None  # Value from database (override)
    default_value: Any | None = None  # Value from schema default
    is_secret: bool = False
    env_var_name: str | None = None

    @computed_field
    @property
    def is_overridden(self) -> bool:
        """True if there is a database override value."""
        return self.db_value is not None

    @computed_field
    @property
    def effective_value(self) -> Any:
        """The effective value using priority hierarchy: db_value > env_value > default_value."""
        if self.db_value is not None:
            return self.db_value
        if self.env_value is not None:
            return self.env_value
        return self.default_value


class ConfigurationDetail(BaseModel):
    """Detailed configuration response with field-level information."""

    key: str
    fields: list[ConfigurationFieldInfo]
    is_valid: bool
    validation_errors: list[str] | None = None


class ConfigService:
    """Service for managing application configuration."""

    def __init__(
        self,
        configuration_repository: ConfigurationRepository,
        config_registry: Registry[type[BaseConfig]] | None = None,
        env_vars: dict[str, str] | None = None,
    ):
        self.config_repo = configuration_repository
        self.config_registry = config_registry or config_schema_registry
        self.env_vars = env_vars if env_vars is not None else dict(os.environ)

    def get_config_by_key(self, key: str) -> BaseConfig | None:
        """Simple getter - returns config if valid, None if not."""
        result = self.validate_config_by_key(key)
        return result.config if result.success else None

    def validate_config_by_key(self, key: str) -> ConfigValidationResult[BaseConfig]:
        """Returns detailed validation result with error information."""
        schema = self.config_registry.get(key)
        if not schema:
            return ConfigValidationResult[BaseConfig](False, errors=[f"No schema registered for key: {key}"])
        return self.validate_config(schema)

    # Type-safe methods for known config types
    def get_config(self, config_class: type[T]) -> T | None:
        """Type-safe getter - returns config if valid, None if not."""
        result = self.validate_config(config_class)
        return result.config if result.success else None

    def validate_config(self, config_class: type[T]) -> ConfigValidationResult[T]:
        """Type-safe validation - returns typed config validation result."""
        try:
            # Load DB data (empty dict if no entry exists)
            db_data = self._load_db_data(self.config_repo, config_class.config_key) or {}

            # Build env var data for this config's fields
            env_prefix = config_class.env_prefix
            env_var_data = {}
            if env_prefix:
                for field_name in config_class.model_fields.keys():
                    env_var_name = f"{env_prefix}{field_name.upper()}"
                    if env_var_name in self.env_vars:
                        env_var_data[field_name] = self.env_vars[env_var_name]

            # Merge env var data with db data (db data takes priority)
            merged_data: dict[str, Any] = {**env_var_data, **db_data}

            # Instantiate config with merged data
            config = config_class(**merged_data)
            return ConfigValidationResult[T](True, config=config)

        except ValidationError as e:
            # Parse errors to provide helpful feedback
            errors: list[str] = []
            for error in e.errors():
                field = error["loc"][0] if error["loc"] else "unknown"
                if "missing" in error["type"]:
                    errors.append(f"Missing required field '{field}'")
                else:
                    errors.append(f"Invalid value for '{field}': {error['msg']}")

            return ConfigValidationResult[T](False, errors=errors)

    def update_configuration(self, key: str, config_data: dict[str, Any]) -> ConfigurationDetail:
        """Update configuration with complete structure. None values clear DB overrides.

        Raises:
            ConfigurationNotFoundError: If no schema is registered for the given key.
        """
        # Get the schema class
        schema_class = self.config_registry.get(key)
        if not schema_class:
            raise ConfigurationNotFoundError(key)

        # Process the complete configuration structure
        # Only store non-None values as database overrides
        db_data = {}
        for field_name, value in config_data.items():
            if value is not None:
                db_data[field_name] = value
            # None values are intentionally not stored (clearing overrides)

        # Save to database
        config = self.config_repo.get_by_key(key)
        if config:
            config.value_json = json.dumps(db_data)
            self.config_repo.update(config)
        else:
            config = Configuration(key=key, value_json=json.dumps(db_data))
            self.config_repo.create(config)

        # Return updated configuration details
        return self.get_config_details(schema_class)

    def list_configs(self, prefix: str | None = None) -> list[str]:
        """List available configuration keys."""
        # Combine with registered schema keys
        all_keys = self.config_registry.list_keys()
        if prefix:
            return [k for k in all_keys if k.startswith(prefix)]
        else:
            return all_keys

    def delete_config(self, key: str) -> None:
        """Delete a configuration."""
        self.config_repo.delete_by_key(key)

    def get_config_details_by_key(self, key: str) -> ConfigurationDetail | None:
        # 1. Get the schema class
        schema_class = self.config_registry.get(key)
        if not schema_class:
            return None
        return self.get_config_details(schema_class)

    def get_config_details(self, schema_class: type[BaseConfig]) -> ConfigurationDetail:
        """Get configuration with field-level source information."""
        # 2. Load raw DB data
        db_data = self._load_db_data(self.config_repo, schema_class.config_key) or {}

        # 3. Get validation result
        validation_result = self.validate_config(schema_class)

        # 4. Analyze each field
        fields = []
        for field_name, field_info in schema_class.model_fields.items():
            # Calculate environment variable name
            env_prefix = schema_class.env_prefix
            if env_prefix:
                env_var_name = f"{env_prefix}{field_name.upper()}"
                # Get values from different sources
                env_value = self.env_vars.get(env_var_name)
            else:
                env_var_name = None
                env_value = None

            db_value = db_data.get(field_name) if field_name in db_data else None
            default_value = field_info.default if field_info.default is not PydanticUndefined else None

            fields.append(
                ConfigurationFieldInfo(
                    name=field_name,
                    type=self._get_field_type(field_info),
                    required=field_info.is_required(),
                    description=field_info.description,
                    env_value=env_value,
                    db_value=db_value,
                    default_value=default_value,
                    is_secret=self._is_secret_field(field_name),
                    env_var_name=env_var_name,
                )
            )

        return ConfigurationDetail(
            key=schema_class.config_key,
            fields=fields,
            is_valid=validation_result.success,
            validation_errors=validation_result.errors,
        )

    def _is_string_field(self, field_info: FieldInfo) -> bool:
        """Check if a field is a string type."""
        # Handle Optional[str], str | None, etc.
        annotation = field_info.annotation
        origin = get_origin(annotation)

        if origin is Union:
            # For Optional[str] or str | None
            args = get_args(annotation)
            return str in args

        return annotation is str

    def _get_field_type(self, field_info: FieldInfo) -> str:
        """Get the field type as a string for UI rendering."""
        annotation = field_info.annotation
        origin = get_origin(annotation)

        # Handle Union types (Optional, etc.)
        if origin is Union:
            args = get_args(annotation)
            # Filter out NoneType for Optional fields
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                annotation = non_none_args[0]

        if annotation is str:
            return "string"
        elif annotation is bool:
            return "boolean"
        elif annotation is int:
            return "integer"
        elif annotation is float:
            return "number"
        else:
            return "string"  # Default fallback

    def _is_secret_field(self, field_name: str) -> bool:
        """Check if a field contains secret/sensitive data."""
        secret_keywords = ["token", "key", "secret", "password", "api_key"]
        field_lower = field_name.lower()
        return any(keyword in field_lower for keyword in secret_keywords)

    def _load_db_data(self, repo: ConfigurationRepository, key: str) -> dict[str, Any] | None:
        """Load configuration data from database using repository."""
        config = repo.get_by_key(key)
        if config:
            return json.loads(config.value_json)
        return None
