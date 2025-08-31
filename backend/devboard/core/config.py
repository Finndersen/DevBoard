"""Generic configuration framework."""

import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from devboard.db.database import SessionLocal
from devboard.db.models import Configuration

T = TypeVar("T", bound=BaseModel)


class ConfigValidationResult:
    """Result of configuration validation with detailed error information."""

    def __init__(
        self,
        success: bool,
        config: BaseModel | None = None,
        errors: list[str] | None = None,
    ):
        self.success = success
        self.config = config
        self.errors = errors or []


class ConfigRepository:
    """Registry of configuration schemas and validation logic."""

    _schemas: dict[str, type[BaseModel]] = {}

    @classmethod
    def register_schema(cls, key: str, schema: type[T]) -> None:
        """Register a Pydantic schema for a configuration key."""
        cls._schemas[key] = schema

    @classmethod
    def get_schema(cls, key: str) -> type[BaseModel] | None:
        """Get the registered schema for a configuration key."""
        return cls._schemas.get(key)

    @classmethod
    def get_all_schemas(cls) -> dict[str, type[BaseModel]]:
        """Get all registered schemas."""
        return cls._schemas.copy()

    @classmethod
    def list_keys(cls, prefix: str | None = None) -> list[str]:
        """List all registered configuration keys, optionally filtered by prefix."""
        keys = list(cls._schemas.keys())
        if prefix:
            keys = [key for key in keys if key.startswith(prefix)]
        return sorted(keys)


class ConfigService:
    """Service for managing application configuration."""

    def __init__(self, db_session_factory=SessionLocal):
        self.db_session_factory = db_session_factory

    def get_config(self, key: str) -> BaseModel | None:
        """Simple getter - returns config if valid, None if not."""
        result = self.validate_config(key)
        return result.config if result.success else None

    def validate_config(self, key: str) -> ConfigValidationResult:
        """Returns detailed validation result with error information."""
        schema = ConfigRepository.get_schema(key)
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
            errors = []
            for error in e.errors():
                field = error["loc"][0] if error["loc"] else "unknown"
                if "missing" in error["type"]:
                    errors.append(
                        f"Missing required field '{field}' - check environment variables or database configuration"
                    )
                else:
                    errors.append(f"Invalid value for '{field}': {error['msg']}")

            return ConfigValidationResult(False, errors=errors)

    def set_config(self, key: str, data: BaseModel) -> None:
        """Set configuration data."""
        # Validate that the key has a registered schema
        schema = ConfigRepository.get_schema(key)
        if not schema:
            raise ValueError(f"No schema registered for key: {key}")

        # Validate the data against the schema
        validated_data = schema.model_validate(data.model_dump())

        # Save to database
        with self.db_session_factory() as db:
            config = db.query(Configuration).filter(Configuration.key == key).first()
            if config:
                config.value_json = validated_data.model_dump_json()
            else:
                config = Configuration(key=key, value_json=validated_data.model_dump_json())
                db.add(config)
            db.commit()

    def list_configs(self, prefix: str | None = None) -> list[str]:
        """List available configuration keys."""
        with self.db_session_factory() as db:
            query = db.query(Configuration.key)
            if prefix:
                query = query.filter(Configuration.key.startswith(prefix))
            db_keys = [row[0] for row in query.all()]

        # Combine with registered schema keys
        schema_keys = ConfigRepository.list_keys(prefix)
        all_keys = sorted(set(db_keys + schema_keys))
        return all_keys

    def delete_config(self, key: str) -> None:
        """Delete a configuration."""
        with self.db_session_factory() as db:
            config = db.query(Configuration).filter(Configuration.key == key).first()
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

    def _load_from_db(self, key: str) -> dict[str, Any] | None:
        """Load configuration data from database."""
        with self.db_session_factory() as db:
            config = db.query(Configuration).filter(Configuration.key == key).first()
            if config:
                return json.loads(config.value_json)
            return None


# Global config service instance
config_service = ConfigService()
