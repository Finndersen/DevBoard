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
    GeminiProviderConfig,
    OpenAIProviderConfig,
)
from devboard.core.registry import Registry
from devboard.config.integration_configs import (
    GitHubIntegrationConfig,
    JiraIntegrationConfig,
    SlackIntegrationConfig,
)

# Create the config schema registry with all schemas
config_schema_registry: Registry[type[BaseConfig]] = Registry([
    # Integration configurations
    GitHubIntegrationConfig,
    JiraIntegrationConfig,
    SlackIntegrationConfig,
    # LLM provider configurations
    OpenAIProviderConfig,
    AnthropicProviderConfig,
    GeminiProviderConfig,
    # Agent configurations
    QAAgentConfig,
    PlanningAgentConfig,
    ImplementationAgentConfig,
    InvestigationAgentConfig,
], key_attr='config_key')


