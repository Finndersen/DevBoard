"""Generic configuration framework."""

from typing import ClassVar, TypeVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    """Base configuration class with common settings for all config models."""

    config_key: ClassVar[str]  # Required class attribute for all config classes

    @classmethod
    def get_base_config(cls, env_prefix: str) -> SettingsConfigDict:
        """Get base model configuration with specified env_prefix."""
        return SettingsConfigDict(
            env_prefix=env_prefix,
            case_sensitive=False,
            extra="forbid",
            validate_assignment=True,
            env_file=".env",
            env_file_encoding="utf-8",
        )


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
