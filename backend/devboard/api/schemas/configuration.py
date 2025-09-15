"""Configuration Pydantic schemas."""

from typing import Any

from pydantic import BaseModel


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

    @property
    def is_overridden(self) -> bool:
        """True if there is a database override value."""
        return self.db_value is not None

    @property
    def effective_value(self) -> Any:
        """The effective value using priority hierarchy: db_value > env_value > default_value."""
        if self.db_value is not None:
            return self.db_value
        if self.env_value is not None:
            return self.env_value
        return self.default_value


class ConfigurationDetailResponse(BaseModel):
    """Detailed configuration response with field-level information."""

    key: str
    fields: list[ConfigurationFieldInfo]
    is_valid: bool
    validation_errors: list[str] | None = None
