"""Service for handling integration operations and testing."""

from dataclasses import dataclass
from typing import TypeVar

import logfire

from devboard.db.repositories import ConfigurationRepository
from devboard.integrations.base import (
    BaseIntegration,
    IntegrationConfigurationError,
    IntegrationError,
)
from devboard.integrations.github import GitHubIntegration
from devboard.integrations.jira import JiraIntegration
from devboard.integrations.slack import SlackIntegration
from devboard.services.config_service import ConfigService

T = TypeVar("T", bound=BaseIntegration)

# All available integration classes
INTEGRATION_CLASSES: list[type[BaseIntegration]] = [
    GitHubIntegration,
    JiraIntegration,
    SlackIntegration,
]

# Mapping from integration type string to class
INTEGRATION_TYPE_MAP: dict[str, type[BaseIntegration]] = {cls.integration_type: cls for cls in INTEGRATION_CLASSES}


class InvalidIntegrationTypeError(Exception):
    """Raised when an invalid integration type is specified."""

    pass


@dataclass
class IntegrationTestResult:
    """Result of integration connection test."""

    integration_type: str
    success: bool
    error_message: str | None = None
    error_type: str | None = None


class IntegrationService:
    """Service for handling integration operations and testing."""

    def __init__(self, config_repository: ConfigurationRepository):
        self.config_repo = config_repository

    async def test_integration_connection(self, integration_type: str) -> IntegrationTestResult:
        """Test connection for a specific integration type.

        Args:
            integration_type: Integration type string (e.g., "github", "jira", "slack")
        """
        with logfire.span("integration_service.test_connection", integration_type=integration_type):
            try:
                integration_class = INTEGRATION_TYPE_MAP.get(integration_type)
                if not integration_class:
                    raise InvalidIntegrationTypeError(f"Unsupported integration type: {integration_type}")

                integration = self.get_integration_instance(integration_class)
                connection_result = await integration.test_connection()

                result = IntegrationTestResult(
                    integration_type=integration_type,
                    success=connection_result.success,
                    error_message=None if connection_result.success else connection_result.message,
                    error_type=None if connection_result.success else "connection_error",
                )

                logfire.info(
                    "Integration test complete",
                    integration_type=integration_type,
                    success=connection_result.success,
                    message=connection_result.message,
                )
                return result

            except InvalidIntegrationTypeError as e:
                logfire.error(
                    "Invalid integration type",
                    integration_type=integration_type,
                    error=str(e),
                    exc_info=e,
                )
                return IntegrationTestResult(
                    integration_type=integration_type,
                    success=False,
                    error_message=str(e),
                    error_type="unsupported_integration",
                )

            except IntegrationConfigurationError as e:
                logfire.error(
                    "Integration configuration error",
                    integration_type=integration_type,
                    error=str(e),
                    exc_info=e,
                )
                return IntegrationTestResult(
                    integration_type=integration_type,
                    success=False,
                    error_message=str(e),
                    error_type="config_error",
                )

    async def test_all_integrations(self) -> dict[str, IntegrationTestResult]:
        """Test connections for all available integration types."""
        with logfire.span(
            "integration_service.test_all_integrations",
            total_integrations=len(INTEGRATION_CLASSES),
        ):
            results: dict[str, IntegrationTestResult] = {}
            for integration_class in INTEGRATION_CLASSES:
                results[integration_class.integration_type] = await self.test_integration_connection(
                    integration_class.integration_type
                )

            successful_count = sum(1 for result in results.values() if result.success)
            logfire.info(
                "All integration tests complete",
                total_integrations=len(results),
                successful_integrations=successful_count,
                failed_integrations=len(results) - successful_count,
            )
            return results

    def get_integration_instance(self, integration_class: type[T]) -> T:
        """Get a configured instance of the specified integration class.

        Args:
            integration_class: The integration class to instantiate (e.g., GitHubIntegration)

        Returns:
            Configured instance of the integration class

        Raises:
            IntegrationConfigurationError: If configuration is missing or invalid
        """
        config_service = ConfigService(self.config_repo)
        config_class = integration_class.configuration_schema
        config = config_service.get_config(config_class)
        if not config:
            raise IntegrationConfigurationError(
                f"{integration_class.integration_type.title()} configuration not found or invalid. "
                f"Please configure the {integration_class.integration_type.title()} integration."
            )

        return integration_class(config)

    async def get_and_verify_integration_instance(self, integration_class: type[T]) -> T:
        """Get a configured instance and verify its connection.

        Combines getting the integration instance with connection verification,
        providing a convenient pattern for code that needs a verified integration.

        Args:
            integration_class: The integration class to instantiate and verify

        Returns:
            Verified instance of the integration class

        Raises:
            IntegrationConfigurationError: If configuration is missing or invalid
            IntegrationError: If connection verification fails
        """
        instance = self.get_integration_instance(integration_class)

        connection_result = await instance.test_connection()
        if not connection_result.success:
            raise IntegrationError(
                f"{integration_class.integration_type.title()} connection failed: {connection_result.message}"
            )

        return instance
