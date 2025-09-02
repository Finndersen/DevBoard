"""Context provider package for intelligent context gathering.

This package provides high-level interfaces for gathering relevant context
from various external sources. Context providers wrap integrations and
provide query-aware, intelligent context extraction capabilities.
"""

from .base import (
    BaseContextProvider,
    ContextProviderError,
    ContextProviderRegistry,
    ContextProviderUnavailable,
    ContextRetrievalError,
    ContextStrategy,
    DescriptionGenerationError,
    ResourceHandlingError,
)
from .codebase import CodebaseContextProvider
from .github import GitHubContextProvider
from .jira import JiraContextProvider
from .slack import SlackContextProvider
from .webpage import WebPageContextProvider


def initialize_context_providers():
    """Initialize and register all context providers.

    This function checks for required configurations, initializes integrations,
    and registers context providers. Providers with missing or invalid
    configurations are skipped with appropriate logging.
    """
    ContextProviderRegistry.register(WebPageContextProvider)
    ContextProviderRegistry.register(GitHubContextProvider)
    ContextProviderRegistry.register(JiraContextProvider)
    ContextProviderRegistry.register(SlackContextProvider)
    ContextProviderRegistry.register(CodebaseContextProvider)


__all__ = [
    # Base classes
    "BaseContextProvider",
    "ContextProviderRegistry",
    # Context providers
    "CodebaseContextProvider",
    "GitHubContextProvider",
    "JiraContextProvider",
    "SlackContextProvider",
    "WebPageContextProvider",
    # Enums
    "ContextStrategy",
    # Exceptions
    "ContextProviderError",
    "ResourceHandlingError",
    "ContextRetrievalError",
    "DescriptionGenerationError",
    "ContextProviderUnavailable",
]
