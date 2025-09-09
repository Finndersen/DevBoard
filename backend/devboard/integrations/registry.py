"""Integration registry for mapping integration type names to classes."""

from devboard.core.registry import Registry

from .base import BaseIntegration
from .github import GitHubIntegration
from .jira import JiraIntegration
from .slack import SlackIntegration

# Module-level singleton instance
integration_registry: Registry[type[BaseIntegration]] = Registry(
    [
        GitHubIntegration,
        JiraIntegration,
        SlackIntegration,
    ],
    key_attr="integration_type",
)
