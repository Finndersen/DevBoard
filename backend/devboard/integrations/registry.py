"""Integration registry for mapping integration type names to classes."""

from .base import BaseIntegration
from .github import GitHubIntegration
from .jira import JiraIntegration
from .slack import SlackIntegration


class IntegrationRegistry:
    """Registry for mapping integration type names to integration classes."""

    _integrations: dict[str, type[BaseIntegration]] = {
        integration.integration_type: integration
        for integration in [
            GitHubIntegration,
            JiraIntegration,
            SlackIntegration,
        ]
    }

    @classmethod
    def get_integration_class(cls, integration_type: str) -> type[BaseIntegration] | None:
        """Get integration class for the given type."""
        return cls._integrations.get(integration_type)

    @classmethod
    def get_available_types(cls) -> list[str]:
        """Get list of available integration types."""
        return list(cls._integrations.keys())

    @classmethod
    def is_supported(cls, integration_type: str) -> bool:
        """Check if integration type is supported."""
        return integration_type in cls._integrations
