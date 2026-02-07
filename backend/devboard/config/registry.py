"""Registry for configuration schemas."""

from devboard.config.base import BaseConfig
from devboard.config.integration_configs import (
    GitHubIntegrationConfig,
    JiraIntegrationConfig,
    SlackIntegrationConfig,
)
from devboard.config.llm_providers import (
    AnthropicProviderConfig,
    GoogleProviderConfig,
    OpenAIProviderConfig,
)
from devboard.core.registry import Registry

# Create the config schema registry with all schemas
config_schema_registry: Registry[type[BaseConfig]] = Registry[type[BaseConfig]](
    [
        # Integration configurations
        GitHubIntegrationConfig,
        JiraIntegrationConfig,
        SlackIntegrationConfig,
        # LLM provider configurations
        OpenAIProviderConfig,
        AnthropicProviderConfig,
        GoogleProviderConfig,
    ],
    key_attr="config_key",
)
