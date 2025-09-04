"""Service for handling integration operations and testing."""

import logging
from dataclasses import dataclass

from devboard.integrations.base import (
    AuthenticationError,
    IntegrationConfigurationError,
    RateLimitError,
)
from devboard.integrations.registry import IntegrationRegistry

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

    async def test_integration_connection(self, integration_type: str) -> IntegrationTestResult:
        """Test connection for a specific integration type."""
        try:
            integration_class = IntegrationRegistry.get_integration_class(integration_type)
            if not integration_class:
                return IntegrationTestResult(
                    integration_type=integration_type,
                    success=False,
                    error_message=f"Unsupported integration type: {integration_type}",
                    error_type="unsupported_integration",
                )

            # Create integration instance
            integration = await integration_class.create()

            # Test connection
            success = await integration.test_connection()

            return IntegrationTestResult(
                integration_type=integration_type,
                success=success,
                error_message=None if success else "Connection test failed",
                error_type=None if success else "connection_error",
            )

        except IntegrationConfigurationError as e:
            logger.error(f"Configuration error for {integration_type}: {e}")
            return IntegrationTestResult(
                integration_type=integration_type,
                success=False,
                error_message=str(e),
                error_type="config_error",
            )
        except AuthenticationError as e:
            logger.error(f"Authentication error for {integration_type}: {e}")
            return IntegrationTestResult(
                integration_type=integration_type,
                success=False,
                error_message=str(e),
                error_type="auth_error",
            )
        except RateLimitError as e:
            logger.error(f"Rate limit error for {integration_type}: {e}")
            return IntegrationTestResult(
                integration_type=integration_type,
                success=False,
                error_message=str(e),
                error_type="rate_limit_error",
            )
        except Exception as e:
            logger.error(f"Unexpected error testing {integration_type}: {e}")
            return IntegrationTestResult(
                integration_type=integration_type,
                success=False,
                error_message=f"Unexpected error: {e}",
                error_type="unknown_error",
            )

    async def test_all_integrations(self) -> dict[str, IntegrationTestResult]:
        """Test connections for all available integration types."""
        results: dict[str, IntegrationTestResult] = {}
        for integration_type in IntegrationRegistry.get_available_types():
            results[integration_type] = await self.test_integration_connection(integration_type)
        return results
