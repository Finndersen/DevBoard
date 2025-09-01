"""Base integration class and common patterns."""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Base exception for integration-related errors."""

    pass


class AuthenticationError(IntegrationError):
    """Raised when authentication fails."""

    pass


class RateLimitError(IntegrationError):
    """Raised when rate limit is exceeded."""

    pass


class ResourceNotFoundError(IntegrationError):
    """Raised when a requested resource is not found."""

    pass


class BaseIntegration(ABC):
    """Abstract base class for all external service integrations."""

    integration_type: str

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection to the external service."""
        pass


class IntegrationRegistry:
    """Registry for managing integration instances."""

    _integrations: dict[str, BaseIntegration] = {}

    @classmethod
    def register(cls, name: str, integration: BaseIntegration) -> None:
        """Register an integration instance."""
        cls._integrations[name] = integration
        logger.info(f"Registered integration: {name}")

    @classmethod
    def get(cls, name: str) -> BaseIntegration | None:
        """Get a registered integration."""
        return cls._integrations.get(name)

    @classmethod
    def list_available(cls) -> list[str]:
        """List all registered integration names."""
        return list(cls._integrations.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered integrations (useful for testing)."""
        cls._integrations.clear()
