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
from devboard.core.registry import Registry
from devboard.integrations.github import GitHubIntegrationConfig
from devboard.integrations.jira import JiraIntegrationConfig
from devboard.integrations.slack import SlackIntegrationConfig

# Create the config schema registry with all schemas
config_schema_registry: Registry[type[BaseConfig]] = Registry([
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
], key_attr='config_key')


