"""Slack integration for accessing messages, channels, and conversations."""

import logging
from typing import Any
from urllib.parse import urlparse

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from devboard.config.integration_configs import SlackIntegrationConfig
from devboard.services.config_service import config_service

from .base import (
    AuthenticationError,
    BaseIntegration,
    IntegrationConfigurationError,
    IntegrationError,
    RateLimitError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


class SlackIntegration(BaseIntegration):
    """Integration for Slack API access."""

    integration_type = "slack"

    def __init__(self, config: SlackIntegrationConfig):
        """Initialize with Slack configuration and client."""
        self.config = config
        try:
            self.client = WebClient(token=config.api_token)
            logger.info("Initialized Slack integration")
        except Exception as e:
            logger.error(f"Failed to initialize Slack integration: {e}")
            raise IntegrationConfigurationError(f"Failed to initialize Slack: {e}") from e

    @classmethod
    def create(cls) -> "SlackIntegration":
        """Create Slack integration instance with configuration from database and environment."""
        try:
            # Get configuration from config service (includes database + environment)
            config = config_service.get_config(SlackIntegrationConfig)
            if not config:
                raise IntegrationConfigurationError(
                    "Slack configuration not found or invalid. Please configure the Slack integration."
                )
            return cls(config)
        except Exception as e:
            logger.error(f"Failed to create Slack integration: {e}")
            raise IntegrationConfigurationError(f"Slack configuration error: {e}") from e

    async def test_connection(self) -> bool:
        """Test Slack API connection."""
        try:
            response = self.client.auth_test()
            return response.get("ok", False)
        except SlackApiError as e:
            if e.response["error"] in ["invalid_auth", "account_inactive", "token_revoked"]:
                raise AuthenticationError(f"Slack authentication failed: {e}") from e
            else:
                logger.error(f"Slack connection test failed: {e}")
                return False
        except Exception as e:
            logger.error(f"Slack connection test failed: {e}")
            return False

    async def get_message(self, channel: str, timestamp: str) -> dict[str, Any] | None:
        """Get a specific message by channel and timestamp."""
        try:
            response = self.client.conversations_history(
                channel=channel, latest=timestamp, inclusive=True, limit=1
            )

            if response.get("ok") and response.get("messages"):
                return response["messages"][0]  # type: ignore[return-value]
            return None
        except SlackApiError as e:
            if e.response["error"] in ["invalid_auth", "account_inactive", "token_revoked"]:
                raise AuthenticationError(f"Slack authentication failed: {e}") from e
            elif e.response["error"] in ["channel_not_found", "not_in_channel"]:
                raise ResourceNotFoundError(f"Channel or message not found: {e}") from e
            elif e.response["error"] == "rate_limited":
                raise RateLimitError(f"Slack rate limit exceeded: {e}") from e
            else:
                logger.error(f"Slack error in get_message({channel}, {timestamp}): {e}")
                raise IntegrationError(f"Slack error: {e}") from e

    async def get_channel_history(
        self,
        channel: str,
        limit: int = 100,
        oldest: str | None = None,
        latest: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get message history from a channel."""
        try:
            response = self.client.conversations_history(
                channel=channel, limit=limit, oldest=oldest, latest=latest
            )

            if response.get("ok"):
                return response.get("messages", [])  # type: ignore[return-value]
            else:
                logger.error(f"Slack API error: {response.get('error')}")
                return []
        except SlackApiError as e:
            if e.response["error"] in ["invalid_auth", "account_inactive", "token_revoked"]:
                raise AuthenticationError(f"Slack authentication failed: {e}") from e
            elif e.response["error"] in ["channel_not_found", "not_in_channel"]:
                raise ResourceNotFoundError(f"Channel not found: {e}") from e
            elif e.response["error"] == "rate_limited":
                raise RateLimitError(f"Slack rate limit exceeded: {e}") from e
            else:
                logger.error(f"Slack error in get_channel_history({channel}): {e}")
                raise IntegrationError(f"Slack error: {e}") from e

    async def get_thread_replies(self, channel: str, thread_ts: str) -> list[dict[str, Any]]:
        """Get replies to a thread."""
        try:
            response = self.client.conversations_replies(channel=channel, ts=thread_ts)

            if response.get("ok"):
                return response.get("messages", [])  # type: ignore[return-value]
            return []
        except SlackApiError as e:
            if e.response["error"] in ["invalid_auth", "account_inactive", "token_revoked"]:
                raise AuthenticationError(f"Slack authentication failed: {e}") from e
            elif e.response["error"] in ["channel_not_found", "thread_not_found"]:
                raise ResourceNotFoundError(f"Channel or thread not found: {e}") from e
            elif e.response["error"] == "rate_limited":
                raise RateLimitError(f"Slack rate limit exceeded: {e}") from e
            else:
                logger.error(f"Slack error in get_thread_replies({channel}, {thread_ts}): {e}")
                raise IntegrationError(f"Slack error: {e}") from e

    async def search_messages(self, query: str, count: int = 20) -> dict[str, Any]:
        """Search messages across the workspace."""
        try:
            response = self.client.search_messages(query=query, count=count)

            if response.get("ok"):
                return response  # type: ignore[return-value]
            else:
                logger.error(f"Slack search error: {response.get('error')}")
                return {"messages": {"matches": []}}
        except SlackApiError as e:
            if e.response["error"] in ["invalid_auth", "account_inactive", "token_revoked"]:
                raise AuthenticationError(f"Slack authentication failed: {e}") from e
            elif e.response["error"] == "rate_limited":
                raise RateLimitError(f"Slack rate limit exceeded: {e}") from e
            else:
                logger.error(f"Slack error in search_messages({query}): {e}")
                raise IntegrationError(f"Slack error: {e}") from e

    async def get_channel_info(self, channel: str) -> dict[str, Any] | None:
        """Get information about a channel."""
        try:
            response = self.client.conversations_info(channel=channel)

            if response.get("ok"):
                return response.get("channel")  # type: ignore[return-value]
            return None
        except SlackApiError as e:
            if e.response["error"] in ["invalid_auth", "account_inactive", "token_revoked"]:
                raise AuthenticationError(f"Slack authentication failed: {e}") from e
            elif e.response["error"] == "channel_not_found":
                raise ResourceNotFoundError(f"Channel not found: {e}") from e
            elif e.response["error"] == "rate_limited":
                raise RateLimitError(f"Slack rate limit exceeded: {e}") from e
            else:
                logger.error(f"Slack error in get_channel_info({channel}): {e}")
                raise IntegrationError(f"Slack error: {e}") from e

    async def list_channels(self, limit: int = 100) -> list[dict[str, Any]]:
        """List public channels."""
        try:
            response = self.client.conversations_list(
                types="public_channel,private_channel", limit=limit
            )

            if response.get("ok"):
                return response.get("channels", [])  # type: ignore[return-value]
            return []
        except SlackApiError as e:
            if e.response["error"] in ["invalid_auth", "account_inactive", "token_revoked"]:
                raise AuthenticationError(f"Slack authentication failed: {e}") from e
            elif e.response["error"] == "rate_limited":
                raise RateLimitError(f"Slack rate limit exceeded: {e}") from e
            else:
                logger.error(f"Slack error in list_channels(): {e}")
                raise IntegrationError(f"Slack error: {e}") from e

    def parse_message_url(self, url: str) -> dict[str, str] | None:
        """Parse Slack message URL to extract channel and timestamp."""
        try:
            # Handle URLs like: https://company.slack.com/archives/C123456/p1234567890123456
            parsed = urlparse(url)
            path_parts = parsed.path.strip("/").split("/")

            if len(path_parts) >= 3 and path_parts[0] == "archives":
                channel = path_parts[1]
                # Convert permalink timestamp to message timestamp
                if path_parts[2].startswith("p"):
                    timestamp_str = path_parts[2][1:]  # Remove 'p' prefix
                    # Convert to proper timestamp format
                    timestamp = f"{timestamp_str[:10]}.{timestamp_str[10:]}"
                    return {"channel": channel, "ts": timestamp}

            return None
        except Exception:
            return None

    def parse_channel_url(self, url: str) -> str | None:
        """Parse Slack channel URL to extract channel ID."""
        try:
            # Handle URLs like: https://company.slack.com/archives/C123456
            parsed = urlparse(url)
            path_parts = parsed.path.strip("/").split("/")

            if len(path_parts) >= 2 and path_parts[0] == "archives":
                return path_parts[1]

            return None
        except Exception:
            return None
