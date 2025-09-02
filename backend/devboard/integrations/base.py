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
