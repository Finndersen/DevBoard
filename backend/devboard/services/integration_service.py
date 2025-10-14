"""Service for handling integration operations and testing."""

from dataclasses import dataclass

import logfire

from devboard.core.registry import Registry
from devboard.db.repositories import ConfigurationRepository
from devboard.integrations.base import (
    BaseIntegration,
    IntegrationConfigurationError,
)
from devboard.integrations.registry import integration_registry
from devboard.services.config_service import ConfigService


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

    def __init__(
        self,
        config_repository: ConfigurationRepository,
        integration_registry_instance: Registry[type[BaseIntegration]] | None = None,
    ):
        self.config_repo = config_repository
        self.integration_registry = integration_registry_instance or integration_registry

    async def test_integration_connection(self, integration_type: str) -> IntegrationTestResult:
        """Test connection for a specific integration type."""
        with logfire.span("integration_service.test_connection", integration_type=integration_type):
            try:
                integration = self.get_integration_instance(integration_type)

                # Test connection
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
        available_types = self.integration_registry.list_keys()
        with logfire.span(
            "integration_service.test_all_integrations",
            total_integrations=len(available_types),
        ):
            results: dict[str, IntegrationTestResult] = {}
            for integration_type in available_types:
                results[integration_type] = await self.test_integration_connection(integration_type)

            successful_count = sum(1 for result in results.values() if result.success)
            logfire.info(
                "All integration tests complete",
                total_integrations=len(results),
                successful_integrations=successful_count,
                failed_integrations=len(results) - successful_count,
            )
            return results

    def get_integration_instance(self, integration_type: str) -> BaseIntegration:
        """Get an instance of the specified integration type."""
        integration_class = self.integration_registry.get(integration_type)
        if not integration_class:
            raise InvalidIntegrationTypeError(f"Unsupported integration type: {integration_type}")

        config_service = ConfigService(self.config_repo)
        config_class = integration_class.configuration_schema
        config = config_service.get_config(config_class)
        if not config:
            raise IntegrationConfigurationError(
                f"{integration_type.title()} configuration not found or invalid. "
                f"Please configure the {integration_type.title()} integration."
            )

        return integration_class(config)
