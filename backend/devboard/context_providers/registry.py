"""Registry for context provider classes."""

from devboard.core.registry import Registry

from .base import BaseContextProvider
from .codebase import CodebaseContextProvider
from .github import GitHubContextProvider
from .jira import JiraContextProvider
from .slack import SlackContextProvider
from .webpage import WebPageContextProvider


class ContextProviderRegistry(Registry[type[BaseContextProvider]]):
    """Registry for context providers with URI-based lookup capability."""

    def get_provider_for_uri(self, resource_uri: str) -> type[BaseContextProvider] | None:
        """Find the first provider that can handle the given resource URI.

        Args:
            resource_uri: The URI to find a provider for

        Returns:
            The provider class that can handle the URI, or None if not found
        """
        for provider in self.list_values():
            if provider.can_handle_uri(resource_uri):
                return provider
        return None


# Module-level singleton instance
context_provider_registry = ContextProviderRegistry(
    [
        CodebaseContextProvider,
        GitHubContextProvider,
        JiraContextProvider,
        SlackContextProvider,
        WebPageContextProvider,
    ],
    key_attr="provider_type",
)
