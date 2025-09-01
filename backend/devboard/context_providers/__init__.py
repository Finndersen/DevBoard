"""Context provider package for intelligent context gathering.

This package provides high-level interfaces for gathering relevant context
from various external sources. Context providers wrap integrations and
provide query-aware, intelligent context extraction capabilities.
"""

from .base import (
    BaseContextProvider,
    ContextProviderError,
    ContextProviderRegistry,
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
    import logging
    import os

    from devboard.core.config import config_service
    from devboard.integrations.base import IntegrationRegistry
    from devboard.integrations.codebase import CodebaseIntegration
    from devboard.integrations.github import GitHubIntegration
    from devboard.integrations.jira import JiraIntegration
    from devboard.integrations.slack import SlackIntegration

    from .codebase import CodebaseContextProvider
    from .github import GitHubContextProvider
    from .jira import JiraContextProvider
    from .slack import SlackContextProvider

    logger = logging.getLogger(__name__)

    # Register web page provider (no dependencies needed)
    webpage_provider = WebPageContextProvider()
    ContextProviderRegistry.register("webpage", webpage_provider)

    # Initialize GitHub provider if configuration is valid
    github_config_result = config_service.validate_config("integration.github.main")
    if github_config_result.success and github_config_result.config:
        try:
            github_integration = GitHubIntegration(github_config_result.config)
            IntegrationRegistry.register("github", github_integration)

            github_provider = GitHubContextProvider(github_integration)
            ContextProviderRegistry.register("github", github_provider)
            logger.info("Initialized GitHub context provider")
        except Exception as e:
            logger.error(f"Failed to initialize GitHub context provider: {e}")
    else:
        logger.info(
            f"Skipping GitHub context provider - configuration invalid: {github_config_result.errors}"
        )

    # Initialize Jira provider if configuration is valid
    jira_config_result = config_service.validate_config("integration.jira.main")
    if jira_config_result.success and jira_config_result.config:
        try:
            jira_integration = JiraIntegration(jira_config_result.config)
            IntegrationRegistry.register("jira", jira_integration)

            jira_provider = JiraContextProvider(jira_integration)
            ContextProviderRegistry.register("jira", jira_provider)
            logger.info("Initialized Jira context provider")
        except Exception as e:
            logger.error(f"Failed to initialize Jira context provider: {e}")
    else:
        logger.info(
            f"Skipping Jira context provider - configuration invalid: {jira_config_result.errors}"
        )

    # Initialize Slack provider if configuration is valid
    slack_config_result = config_service.validate_config("integration.slack.main")
    if slack_config_result.success and slack_config_result.config:
        try:
            slack_integration = SlackIntegration(slack_config_result.config)
            IntegrationRegistry.register("slack", slack_integration)

            slack_provider = SlackContextProvider(slack_integration)
            ContextProviderRegistry.register("slack", slack_provider)
            logger.info("Initialized Slack context provider")
        except Exception as e:
            logger.error(f"Failed to initialize Slack context provider: {e}")
    else:
        logger.info(
            f"Skipping Slack context provider - configuration invalid: {slack_config_result.errors}"
        )

    # Initialize Codebase provider (no configuration required, uses current working directory)
    try:
        current_dir = os.getcwd()
        codebase_integration = CodebaseIntegration(current_dir)
        IntegrationRegistry.register("codebase", codebase_integration)

        codebase_provider = CodebaseContextProvider(codebase_integration)
        ContextProviderRegistry.register("codebase", codebase_provider)
        logger.info("Initialized Codebase context provider")
    except Exception as e:
        logger.error(f"Failed to initialize Codebase context provider: {e}")


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
]
