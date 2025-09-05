"""Service for managing application configuration."""

import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select

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
