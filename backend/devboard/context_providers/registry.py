"""Registry for context provider classes."""

from devboard.context_providers.base import BaseContextProvider
from devboard.context_providers.codebase import CodebaseContextProvider
from devboard.context_providers.github import GitHubContextProvider
from devboard.context_providers.jira import JiraContextProvider
from devboard.context_providers.slack import SlackContextProvider
from devboard.context_providers.webpage import WebPageContextProvider


class ContextProviderRegistry:
    """Registry for managing context provider classes."""

    _providers: dict[str, type[BaseContextProvider]] = {
        provider.provider_type: provider
        for provider in [
            CodebaseContextProvider,
            GitHubContextProvider,
            JiraContextProvider,
            SlackContextProvider,
            WebPageContextProvider,
        ]
    }

    @classmethod
    def get(cls, name: str) -> type[BaseContextProvider] | None:
        """Get a registered context provider class.

        Args:
            name: The provider type name to look up

        Returns:
            The provider class if found, None otherwise
        """
        return cls._providers.get(name)

    @classmethod
    def list_available(cls) -> list[str]:
        """List all registered context provider names."""
        return list(cls._providers.keys())

    @classmethod
    def get_provider_for_uri(cls, resource_uri: str) -> type[BaseContextProvider] | None:
        """Find the first provider class that can handle the given resource URI.

        Args:
            resource_uri: The URI to find a provider for

        Returns:
            The provider class that can handle the URI, or None if not found
        """
        for provider_class in cls._providers.values():
            if provider_class.can_handle_uri(resource_uri):
                return provider_class
        return None

    @classmethod
    def register(cls, provider_class: type[BaseContextProvider]) -> None:
        """Register a context provider class (for testing purposes only).

        Note: In production, providers are automatically registered via the self-building
        registry pattern. This method is provided for test mock registration.

        Args:
            provider_class: The context provider class to register

        Raises:
            ValueError: If provider class doesn't have provider_type attribute
        """
        if not hasattr(provider_class, "provider_type"):
            raise ValueError("Provider class must have 'provider_type' attribute")
        cls._providers[provider_class.provider_type] = provider_class

    @classmethod
    def clear(cls) -> None:
        """Clear all registered providers (useful for testing)."""
        cls._providers.clear()
