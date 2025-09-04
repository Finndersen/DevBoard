"""Context provider package for intelligent context gathering.

This package provides high-level interfaces for gathering relevant context
from various external sources. Context providers wrap integrations and
provide query-aware, intelligent context extraction capabilities.
"""

from .base import (
    BaseContextProvider,
    ContextProviderError,
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

__all__ = [
    # Base classes
    "BaseContextProvider",
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
