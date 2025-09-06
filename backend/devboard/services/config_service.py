"""Service for managing application configuration."""

import json
import os
from typing import Any, Union, get_args, get_origin

from pydantic import ValidationError
from pydantic.fields import FieldInfo, PydanticUndefined
from sqlalchemy import select

from devboard.api.schemas.configuration import ConfigurationDetailResponse, ConfigurationFieldInfo
from devboard.config.base import BaseConfig, ConfigValidationResult
from devboard.config.registry import config_schema_registry
from devboard.db.database import SessionLocal, SessionMakerType
from devboard.db.models import Configuration


class ConfigService:
    """Service for managing application configuration."""

    def __init__(self, db_session_factory: SessionMakerType = SessionLocal, config_registry=None):
        self.db_session_factory = db_session_factory
        self.config_registry = config_registry or config_schema_registry

    def get_config(self, key: str) -> BaseConfig | None:
        """Simple getter - returns config if valid, None if not."""
        result = self.validate_config(key)
        return result.config if result.success else None

    def validate_config(self, key: str) -> ConfigValidationResult:
        """Returns detailed validation result with error information."""
        schema = self.config_registry.get(key)
        if not schema:
            return ConfigValidationResult(False, errors=[f"No schema registered for key: {key}"])

        try:
            # Load DB data (empty dict if no entry exists)
            db_data = self._load_from_db(key) or {}

            # Attempt to instantiate with DB + env vars
            config = schema.model_validate(db_data)
            return ConfigValidationResult(True, config=config)

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

            return ConfigValidationResult(False, errors=errors)

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
                config = Configuration(key=key, value_json=validated_data.model_dump_json())
                db.add(config)
            db.commit()

    def update_config_fields(self, key: str, field_updates: dict[str, Any]) -> ConfigurationDetailResponse:
        """Update only specific configuration fields, respecting environment variable precedence."""
        # Get the schema class
        schema_class = self.config_registry.get(key)
        if not schema_class:
            raise ValueError(f"No schema registered for key: {key}")

        # Get current configuration details to check field sources
        current_details = self.get_config_details(key)

        # Load existing DB data
        db_data = self._load_from_db(key) or {}

        # Filter out fields that are set by environment variables
        allowed_updates = {}
        rejected_fields = []

        for field_name, new_value in field_updates.items():
            # Find the field info from current details
            field_info = next((f for f in current_details.fields if f.name == field_name), None)

            if field_info and field_info.value_source == "environment":
                # Don't allow updating fields that are set by environment variables
                rejected_fields.append(field_name)
            else:
                # Allow updating fields from database or default sources
                allowed_updates[field_name] = new_value

        if rejected_fields:
            raise ValueError(
                f"Cannot update fields set by environment variables: {', '.join(rejected_fields)}"
            )

        # Update the database data with allowed updates
        db_data.update(allowed_updates)

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

    def get_provider_status(self, provider_type: str) -> dict[str, ConfigValidationResult]:
        """Check all configs needed for a provider type."""
        # Get all config keys that start with the provider type
        integration_key = f"integration.{provider_type}.main"
        context_provider_key = f"context_provider.{provider_type}.default"

        return {
            "integration": self.validate_config(integration_key),
            "context_provider": self.validate_config(context_provider_key),
        }

    def get_config_details(self, key: str) -> ConfigurationDetailResponse:
        """Get configuration with field-level source information."""
        # 1. Get the schema class
        schema_class = self.config_registry.get(key)
        if not schema_class:
            return ConfigurationDetailResponse(
                key=key,
                fields=[],
                validation_status="unconfigured",
                validation_errors=[f"No schema registered for key: {key}"]
            )

        # 2. Load raw DB data
        db_data = self._load_from_db(key) or {}

        # 3. Get final merged config (or validation errors)
        validation_result = self.validate_config(key)
        final_config = validation_result.config

        # 4. Analyze each field
        fields = []
        for field_name, field_info in schema_class.model_fields.items():
            env_var_name = None
            value_source = None
            current_value = None
            env_value_present = False

            # Only check env vars for string fields
            is_string_field = self._is_string_field(field_info)

            if is_string_field:
                env_prefix = schema_class.model_config.get('env_prefix', '')
                env_var_name = f"{env_prefix}{field_name.upper()}"
                env_value_present = env_var_name in os.environ

            if final_config:
                current_value = getattr(final_config, field_name)

                # Determine source
                if is_string_field and env_value_present:
                    # For string fields, check if env value matches current value
                    env_value = os.environ[env_var_name]
                    if current_value == env_value:
                        value_source = "environment"
                    elif field_name in db_data:
                        # DB override of env var
                        value_source = "database"
                elif field_name in db_data:
                    # DB value (no env var possible for non-strings)
                    value_source = "database"
                elif current_value == field_info.default:
                    value_source = "default"

            fields.append(ConfigurationFieldInfo(
                name=field_name,
                type=self._get_field_type(field_info),
                required=field_info.is_required(),
                description=field_info.description,
                current_value=current_value,
                value_source=value_source,
                is_secret=self._is_secret_field(field_name),
                env_var_name=env_var_name,  # Only set for string fields
                default_value=field_info.default if field_info.default is not PydanticUndefined else None,
                env_value_present=env_value_present
            ))

        return ConfigurationDetailResponse(
            key=key,
            fields=fields,
            validation_status="valid" if validation_result.success else "invalid",
            validation_errors=validation_result.errors
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
        secret_keywords = ['token', 'key', 'secret', 'password', 'api_key']
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
