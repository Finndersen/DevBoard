"""Base integration class and common patterns."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from devboard.config.base import BaseConfig

logger = logging.getLogger(__name__)


@dataclass
class IntegrationConnectionResult:
    """Result of integration connection test."""

    success: bool
    message: str


class IntegrationError(Exception):
    """Base exception for integration-related errors."""

    pass


class IntegrationConfigurationError(IntegrationError):
    """Raised when integration cannot initialize due to missing/invalid config."""

    pass


class UnsupportedIntegrationError(IntegrationError):
    """Raised when integration type is not supported."""

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


class ConnectionError(IntegrationError):
    """Raised when a connection to an external service fails."""

    pass


class BaseIntegration(ABC):
    """Abstract base class for all external service integrations."""

    integration_type: str
    configuration_schema: type[BaseConfig]

    def __init__(self, config: BaseConfig):
        """Initialize with configuration."""
        self.config = config

    @abstractmethod
    async def test_connection(self) -> IntegrationConnectionResult:
        """Test the connection to the external service."""
        pass
