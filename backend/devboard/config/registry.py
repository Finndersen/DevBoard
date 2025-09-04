"""Registry for configuration schemas."""

from devboard.config.agent_config import (
    ImplementationAgentConfig,
    InvestigationAgentConfig,
    PlanningAgentConfig,
    QAAgentConfig,
)
from devboard.config.base import BaseConfig
from devboard.config.llm_config import (
    AnthropicProviderConfig,
    GoogleProviderConfig,
    OpenAIProviderConfig,
)
from devboard.integrations.github import GitHubIntegrationConfig
from devboard.integrations.jira import JiraIntegrationConfig
from devboard.integrations.slack import SlackIntegrationConfig


class ConfigRegistry:
    """Registry of configuration schemas and validation logic."""

    _schemas: dict[str, type[BaseConfig]] = {
        schema.config_key: schema
        for schema in [
            # Integration configurations
            GitHubIntegrationConfig,
            JiraIntegrationConfig,
            SlackIntegrationConfig,
            # LLM provider configurations
            OpenAIProviderConfig,
            AnthropicProviderConfig,
            GoogleProviderConfig,
            # Agent configurations
            QAAgentConfig,
            PlanningAgentConfig,
            ImplementationAgentConfig,
            InvestigationAgentConfig,
        ]
    }

    @classmethod
    def get_schema(cls, key: str) -> type[BaseConfig] | None:
        """Get the registered schema for a configuration key."""
        return cls._schemas.get(key)

    @classmethod
    def get_all_schemas(cls) -> dict[str, type[BaseConfig]]:
        """Get all registered schemas."""
        return cls._schemas.copy()

    @classmethod
    def list_keys(cls, prefix: str | None = None) -> list[str]:
        """List all registered configuration keys, optionally filtered by prefix."""
        keys = list(cls._schemas.keys())
        if prefix:
            keys = [key for key in keys if key.startswith(prefix)]
        return sorted(keys)
