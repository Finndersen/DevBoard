"""Generic configuration framework."""

from typing import ClassVar, TypeVar

from pydantic import BaseModel


class BaseConfig(BaseModel):
    """Base configuration class with common settings for all config models."""

    config_key: ClassVar[str]  # Required class attribute for all config classes
    env_prefix: ClassVar[str | None] = None  # Optional env var prefix


T = TypeVar("T", bound=BaseConfig)


class ConfigValidationResult[T: BaseConfig]:
    """Result of configuration validation with detailed error information."""

    def __init__(
        self,
        success: bool,
        config: T | None = None,
        errors: list[str] | None = None,
    ):
        self.success = success
        self.config = config
        self.errors = errors or []
