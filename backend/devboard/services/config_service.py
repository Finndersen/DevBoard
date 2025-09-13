"""Service for managing application configuration."""

import json
import os
from typing import Any, TypeVar, Union, cast, get_args, get_origin

from pydantic import ValidationError
from pydantic._internal._fields import PydanticUndefined
from pydantic.fields import FieldInfo
from sqlalchemy import select

from devboard.api.schemas.configuration import (
    ConfigurationDetailResponse,
    ConfigurationFieldInfo,
)
from devboard.config.base import BaseConfig, ConfigValidationResult
from devboard.config.registry import config_schema_registry
from devboard.core.registry import Registry
from devboard.db.database import SessionLocal, SessionMakerType
from devboard.db.models import Configuration

T = TypeVar("T", bound="BaseConfig")


class ConfigService:
    """Service for managing application configuration."""

    def __init__(
        self,
        db_session_factory: SessionMakerType = SessionLocal,
        config_registry: Registry[type[BaseConfig]] | None = None,
    ):
        self.db_session_factory = db_session_factory
        self.config_registry = config_registry or config_schema_registry

    def get_config_by_key(self, key: str) -> BaseConfig | None:
        """Simple getter - returns config if valid, None if not."""
        result = self.validate_config_by_key(key)
        return result.config if result.success else None

    def validate_config_by_key(self, key: str) -> ConfigValidationResult[BaseConfig]:
        """Returns detailed validation result with error information."""
        schema = self.config_registry.get(key)
        if not schema:
            return ConfigValidationResult[BaseConfig](
                False, errors=[f"No schema registered for key: {key}"]
            )

        try:
            # Load DB data (empty dict if no entry exists)
            db_data = self._load_from_db(key) or {}

            # Attempt to instantiate with DB + env vars
            config = schema.model_validate(db_data)
            return ConfigValidationResult[BaseConfig](True, config=config)

        except ValidationError as e:
            # Parse errors to provide helpful feedback
            errors: list[str] = []
            for error in e.errors():
                field = error["loc"][0] if error["loc"] else "unknown"
                if "missing" in error["type"]:
                    errors.append(
                        f"Missing required field '{field}' - check environment variables or database configuration"
                    )
                else:
                    errors.append(f"Invalid value for '{field}': {error['msg']}")

            return ConfigValidationResult[BaseConfig](False, errors=errors)

    # Type-safe methods for known config types
    def get_config(self, config_class: type[T]) -> T | None:
        """Type-safe getter - returns config if valid, None if not."""
        result = self.validate_config(config_class)
        return result.config if result.success else None

    def validate_config(self, config_class: type[T]) -> ConfigValidationResult[T]:
        """Type-safe validation - returns typed config validation result."""
        key = config_class.config_key
        result = self.validate_config_by_key(key)
        if result.success:
            return ConfigValidationResult[T](True, config=cast(T, result.config))
        return ConfigValidationResult[T](False, errors=result.errors)

    def set_config(self, key: str, data: BaseConfig) -> None:
        """Set configuration data."""
        # Validate that the key has a registered schema
        schema = self.config_registry.get(key)
        if not schema:
            raise ValueError(f"No schema registered for key: {key}")

        # Validate the data against the schema
        validated_data = schema.model_validate(data.model_dump())

        # Save to database
        with self.db_session_factory() as db:
            stmt = select(Configuration).where(Configuration.key == key)
            config = db.execute(stmt).scalar_one_or_none()
            if config:
                config.value_json = validated_data.model_dump_json()
            else:
                config = Configuration(
                    key=key, value_json=validated_data.model_dump_json()
                )
                db.add(config)
            db.commit()

    def update_config_fields(
        self, key: str, field_updates: dict[str, Any]
    ) -> ConfigurationDetailResponse:
        """Update only specific configuration fields, respecting environment variable precedence."""
        # Get the schema class
        schema_class = self.config_registry.get(key)
        if not schema_class:
            raise ValueError(f"No schema registered for key: {key}")

        # Load existing DB data
        db_data = self._load_from_db(key) or {}

        # Allow updating all fields - users can override environment variables
        # Convert empty strings to None and remove from database (reset to env/default)
        for field_name, value in field_updates.items():
            if isinstance(value, str) and value.strip() == "":
                # Remove from database to reset to environment or default value
                db_data.pop(field_name, None)
            elif value is None:
                # Explicit None means remove from database
                db_data.pop(field_name, None)
            else:
                # Set the value in database
                db_data[field_name] = value

        # Save updated data to database
        with self.db_session_factory() as db:
            stmt = select(Configuration).where(Configuration.key == key)
            config = db.execute(stmt).scalar_one_or_none()
            if config:
                config.value_json = json.dumps(db_data)
            else:
                config = Configuration(key=key, value_json=json.dumps(db_data))
                db.add(config)
            db.commit()

        # Return updated configuration details
        return self.get_config_details(key)

    def list_configs(self, prefix: str | None = None) -> list[str]:
        """List available configuration keys."""
        with self.db_session_factory() as db:
            stmt = select(Configuration.key)
            if prefix:
                stmt = stmt.where(Configuration.key.startswith(prefix))
            db_keys = list(db.execute(stmt).scalars().all())

        # Combine with registered schema keys
        schema_keys = self.config_registry.list_keys()
        all_keys = sorted(set(db_keys + schema_keys))
        return all_keys

    def delete_config(self, key: str) -> None:
        """Delete a configuration."""
        with self.db_session_factory() as db:
            stmt = select(Configuration).where(Configuration.key == key)
            config = db.execute(stmt).scalar_one_or_none()
            if config:
                db.delete(config)
                db.commit()

    def get_config_details(self, key: str) -> ConfigurationDetailResponse:
        """Get configuration with field-level source information."""
        # 1. Get the schema class
        schema_class = self.config_registry.get(key)
        if not schema_class:
            return ConfigurationDetailResponse(
                key=key,
                fields=[],
                validation_status="unconfigured",
                validation_errors=[f"No schema registered for key: {key}"],
            )

        # 2. Load raw DB data
        db_data = self._load_from_db(key) or {}

        # 3. Get final merged config (or validation errors)
        validation_result = self.validate_config(key)
        final_config = validation_result.config

        # 4. Analyze each field
        fields = []
        for field_name, field_info in schema_class.model_fields.items():
            value_source = None
            current_value = None

            # Calculate environment variable name for all fields
            env_prefix = schema_class.model_config.get("env_prefix", "")
            env_var_name = f"{env_prefix}{field_name.upper()}"
            env_value_present = env_var_name in os.environ

            # Only check env vars for string fields for value comparison
            is_string_field = self._is_string_field(field_info)

            if final_config:
                current_value = getattr(final_config, field_name)

                # Determine source - simplified logic
                if field_name in db_data:
                    # Database value takes precedence (could be overriding env var)
                    value_source = "database"
                elif is_string_field and env_value_present:
                    # String field using environment variable
                    value_source = "environment"
                elif current_value == field_info.default:
                    # Using default value
                    value_source = "default"

            fields.append(
                ConfigurationFieldInfo(
                    name=field_name,
                    type=self._get_field_type(field_info),
                    required=field_info.is_required(),
                    description=field_info.description,
                    current_value=current_value,
                    value_source=value_source,
                    is_secret=self._is_secret_field(field_name),
                    env_var_name=env_var_name,  # Now set for all fields
                    default_value=field_info.default
                    if field_info.default is not PydanticUndefined
                    else None,
                    env_value_present=env_value_present,
                )
            )

        return ConfigurationDetailResponse(
            key=key,
            fields=fields,
            validation_status="valid" if validation_result.success else "invalid",
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

    def _load_from_db(self, key: str) -> dict[str, Any] | None:
        """Load configuration data from database."""
        with self.db_session_factory() as db:
            stmt = select(Configuration).where(Configuration.key == key)
            config = db.execute(stmt).scalar_one_or_none()
            if config:
                return json.loads(config.value_json)
            return None


# Global config service instance
config_service = ConfigService()
