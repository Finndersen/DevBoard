"""Base context provider class and common patterns."""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ContextStrategy(str, Enum):
    """Strategy for context retrieval from a resource."""

    EAGER = "EAGER"
    """Small-scope resources that can be loaded fully in advance."""

    ON_DEMAND = "ON_DEMAND"
    """Large-scope resources that require query-specific context extraction."""


class ContextProviderError(Exception):
    """Base exception for context provider-related errors."""

    pass


class ResourceHandlingError(ContextProviderError):
    """Raised when a resource URI cannot be handled by the provider."""

    pass


class ContextRetrievalError(ContextProviderError):
    """Raised when context cannot be retrieved for a resource."""

    pass


class DescriptionGenerationError(ContextProviderError):
    """Raised when resource description cannot be generated."""

    pass


class ContextProviderUnavailable(ContextProviderError):
    """Raised when a provider cannot be initialized due to missing/invalid configuration."""

    pass


class BaseContextProvider(ABC):
    """Abstract base class for all context providers.

    Context providers wrap integrations and provide higher-level, query-aware
    context gathering capabilities. They act as intelligent interfaces between
    raw integration data and AI agents.
    """

    provider_type: str

    @classmethod
    @abstractmethod
    def create_instance(cls) -> "BaseContextProvider":
        """Create a configured instance of this provider.

        This factory method handles provider-specific initialization,
        including configuration validation and integration setup.

        Returns:
            Configured provider instance ready for use

        Raises:
            ContextProviderUnavailable: If provider cannot be initialized
                due to missing or invalid configuration
        """
        pass

    @classmethod
    @abstractmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        """Determine if this provider can handle the given resource URI.

        Args:
            resource_uri: The URI of the resource to check (e.g., Slack channel link,
                         GitHub PR URL, Jira issue URL, file path).

        Returns:
            True if this provider can handle the resource, False otherwise.
        """
        pass

    @abstractmethod
    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        """Determine the retrieval strategy for the given resource.

        Args:
            resource_uri: The URI of the resource to check.

        Returns:
            EAGER for small-scope resources that can be loaded fully,
            ON_DEMAND for large-scope resources requiring query-specific extraction.

        Raises:
            ResourceHandlingError: If the resource URI cannot be handled by this provider.
        """
        pass

    @abstractmethod
    async def get_resource(self, resource_uri: str) -> dict[str, Any]:
        """Retrieve full content for small-scope resources (EAGER strategy).

        This method should only be called for resources with EAGER strategy.
        It returns the complete resource data for inclusion in agent context.

        Args:
            resource_uri: The URI of the resource to retrieve.

        Returns:
            Dictionary containing the full resource data.

        Raises:
            ResourceHandlingError: If the resource URI cannot be handled.
            ContextRetrievalError: If the resource content cannot be retrieved.
        """
        pass

    @abstractmethod
    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        """Universal query interface for ON_DEMAND context extraction.

        This is the primary method for intelligent context gathering. It uses
        internal sub-agents to process high-level queries and return focused
        summaries relevant to the query.

        Args:
            resource_uri: The URI of the resource to query.
            query: The specific query or question about the resource.

        Returns:
            Focused context summary relevant to the query.

        Raises:
            ResourceHandlingError: If the resource URI cannot be handled.
            ContextRetrievalError: If relevant context cannot be extracted.
        """
        pass

    @abstractmethod
    async def generate_resource_description(self, resource_uri: str) -> str:
        """Generate or retrieve a description for the given resource.

        This method provides a human-readable description of what the resource
        contains, which helps agents decide whether to query it and helps users
        understand what resources are available.

        Args:
            resource_uri: The URI of the resource to describe.

        Returns:
            Human-readable description of the resource content and purpose.

        Raises:
            ResourceHandlingError: If the resource URI cannot be handled.
            DescriptionGenerationError: If a description cannot be generated.
        """
        pass

    async def get_integration_tools(self) -> list[Any]:
        """Get lower-level integration tools for write operations.

        This method returns integration tools that can be used by implementation
        agents for write operations like updating Jira status or creating GitHub PRs.
        The default implementation returns an empty list, indicating no write tools.

        Returns:
            List of integration tool instances for write operations.
        """
        return []


class ContextProviderRegistry:
    """Registry for managing context provider classes only."""

    _providers: dict[str, type[BaseContextProvider]] = {}

    @classmethod
    def register(cls, provider_class: type[BaseContextProvider]) -> None:
        """Register a context provider class.

        Args:
            provider_class: The context provider class to register

        Raises:
            ValueError: If provider class doesn't have provider_type attribute
        """
        if not hasattr(provider_class, "provider_type"):
            raise ValueError("Provider class must have 'provider_type' attribute")
        cls._providers[provider_class.provider_type] = provider_class

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
    def clear(cls) -> None:
        """Clear all registered providers (useful for testing)."""
        cls._providers.clear()
