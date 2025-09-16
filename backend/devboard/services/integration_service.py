"""Service for handling integration operations and testing."""

import logging
from dataclasses import dataclass

import logfire

from devboard.core.registry import Registry
from devboard.db.repositories import ConfigurationRepository
from devboard.integrations.base import (
    AuthenticationError,
    BaseIntegration,
    ConnectionError,
    IntegrationConfigurationError,
    RateLimitError,
)
from devboard.integrations.registry import integration_registry
from devboard.services.config_service import ConfigService

logger = logging.getLogger(__name__)


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
                integration_class = self.integration_registry.get(integration_type)
                if not integration_class:
                    logfire.warn(
                        "Unsupported integration type",
                        integration_type=integration_type,
                    )
                    return IntegrationTestResult(
                        integration_type=integration_type,
                        success=False,
                        error_message=f"Unsupported integration type: {integration_type}",
                        error_type="unsupported_integration",
                    )

                # Create integration instance
                with logfire.span("integration_service.create_instance"):
                    config_service = ConfigService(self.config_repo)
                    integration = integration_class.create(config_service)

                # Test connection
                with logfire.span("integration_service.test_api_connection"):
                    success = await integration.test_connection()

                result = IntegrationTestResult(
                    integration_type=integration_type,
                    success=success,
                    error_message=None if success else "Connection test failed",
                    error_type=None if success else "connection_error",
                )

                logfire.info(
                    "Integration test complete",
                    integration_type=integration_type,
                    success=success,
                )
                return result

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
            except AuthenticationError as e:
                logfire.error(
                    "Integration authentication error",
                    integration_type=integration_type,
                    error=str(e),
                    exc_info=e,
                )
                return IntegrationTestResult(
                    integration_type=integration_type,
                    success=False,
                    error_message=str(e),
                    error_type="auth_error",
                )
            except RateLimitError as e:
                logfire.error(
                    "Integration rate limit error",
                    integration_type=integration_type,
                    error=str(e),
                    exc_info=e,
                )
                return IntegrationTestResult(
                    integration_type=integration_type,
                    success=False,
                    error_message=str(e),
                    error_type="rate_limit_error",
                )
            except ConnectionError as e:
                logfire.error(
                    "Integration connection error",
                    integration_type=integration_type,
                    error=str(e),
                    exc_info=e,
                )
                return IntegrationTestResult(
                    integration_type=integration_type,
                    success=False,
                    error_message=str(e),
                    error_type="connection_error",
                )
            except Exception as e:
                logfire.error(
                    "Unexpected integration test error",
                    integration_type=integration_type,
                    error=str(e),
                    exc_info=e,
                )
                return IntegrationTestResult(
                    integration_type=integration_type,
                    success=False,
                    error_message=f"Unexpected error: {e}",
                    error_type="unknown_error",
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
