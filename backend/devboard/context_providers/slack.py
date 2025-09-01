"""Slack context provider for message, channel, and conversation context."""

import logging
from typing import Any
from urllib.parse import urlparse

from devboard.integrations.slack import SlackIntegration

from .base import (
    BaseContextProvider,
    ContextRetrievalError,
    ContextStrategy,
    DescriptionGenerationError,
    ResourceHandlingError,
)

logger = logging.getLogger(__name__)


class SlackContextProvider(BaseContextProvider):
    """Context provider for Slack resources (messages, channels, conversations)."""

    provider_type = "slack"

    def __init__(self, integration: SlackIntegration):
        """Initialize with Slack integration."""
        self.integration = integration

    def can_handle_uri(self, resource_uri: str) -> bool:
        """Check if URI is a Slack resource."""
        try:
            parsed = urlparse(resource_uri)
            return (
                "slack.com" in parsed.netloc
                or resource_uri.startswith("#")
                or resource_uri.startswith("@")
            )
        except Exception:
            return False

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        """Slack messages are EAGER, channels/workspaces are ON_DEMAND."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        # Specific message links are small enough for EAGER loading
        if "/archives/" in resource_uri and "/p" in resource_uri:
            return ContextStrategy.EAGER
        # Channels and general workspace are ON_DEMAND
        return ContextStrategy.ON_DEMAND

    def _parse_slack_url(self, url: str) -> dict[str, str] | None:
        """Parse Slack URL to extract components."""
        try:
            # Handle different Slack URL formats
            if url.startswith("#"):
                return {"type": "channel", "channel": url[1:]}
            elif url.startswith("@"):
                return {"type": "dm", "user": url[1:]}

            # Parse full Slack URLs
            message_parts = self.integration.parse_message_url(url)
            if message_parts:
                return {"type": "message", **message_parts}

            channel_id = self.integration.parse_channel_url(url)
            if channel_id:
                return {"type": "channel", "channel": channel_id}

            return None
        except Exception:
            return None

    async def get_resource(self, resource_uri: str) -> dict[str, Any]:
        """Get full resource data for EAGER strategy (specific messages)."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            parsed = self._parse_slack_url(resource_uri)
            if not parsed:
                raise ResourceHandlingError(f"Invalid Slack URL format: {resource_uri}")

            if parsed["type"] == "message":
                message_data = await self.integration.get_message(parsed["channel"], parsed["ts"])
                if not message_data:
                    raise ContextRetrievalError("Message not found")

                # Get thread replies if this is a threaded message
                thread_replies = []
                if message_data.get("reply_count", 0) > 0:
                    thread_replies = await self.integration.get_thread_replies(
                        parsed["channel"], parsed["ts"]
                    )

                return {
                    "message": message_data,
                    "thread_replies": thread_replies,
                    "uri": resource_uri,
                }
            else:
                raise ResourceHandlingError("get_resource only supports specific messages")

        except Exception as e:
            if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                raise
            logger.error(f"Error getting Slack resource for {resource_uri}: {e}")
            raise ContextRetrievalError(f"Failed to get Slack resource: {e}") from e

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        """Get query-relevant context from Slack resource."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            parsed = self._parse_slack_url(resource_uri)
            if not parsed:
                raise ResourceHandlingError(f"Invalid Slack URL format: {resource_uri}")

            if parsed["type"] == "message":
                message_data = await self.integration.get_message(parsed["channel"], parsed["ts"])
                if not message_data:
                    raise ContextRetrievalError("Message not found")

                thread_replies = []
                if message_data.get("reply_count", 0) > 0:
                    thread_replies = await self.integration.get_thread_replies(
                        parsed["channel"], parsed["ts"]
                    )

                context = f"""
Slack Message
Channel: {parsed.get("channel", "unknown")}
URL: {resource_uri}
Author: {message_data.get("user", "unknown")}
Timestamp: {message_data.get("ts", "unknown")}
Text: {message_data.get("text", "No text")}

Thread Replies: {len(thread_replies)} replies

Query: {query}

Based on this Slack message and thread, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                return context

            elif parsed["type"] == "channel":
                channel_info = await self.integration.get_channel_info(parsed["channel"])
                if not channel_info:
                    raise ContextRetrievalError("Channel not found")

                # Get recent messages for context
                recent_messages = await self.integration.get_channel_history(
                    parsed["channel"], limit=50
                )

                context = f"""
Slack Channel: {channel_info.get("name", "unknown")}
URL: {resource_uri}
Purpose: {channel_info.get("purpose", {}).get("value", "No purpose set")}
Topic: {channel_info.get("topic", {}).get("value", "No topic set")}
Members: {channel_info.get("num_members", 0)} members

Recent Messages: {len(recent_messages)} messages loaded

Query: {query}

Based on this channel and recent messages, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                return context
            else:
                raise ResourceHandlingError(
                    f"Unsupported Slack resource type: {parsed.get('type')}"
                )

        except Exception as e:
            if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                raise
            logger.error(f"Error getting Slack context for {resource_uri}: {e}")
            raise ContextRetrievalError(f"Failed to get Slack context: {e}") from e

    async def generate_resource_description(self, resource_uri: str) -> str:
        """Generate description for Slack resource."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            parsed = self._parse_slack_url(resource_uri)
            if not parsed:
                raise ResourceHandlingError(f"Invalid Slack URL format: {resource_uri}")

            if parsed["type"] == "message":
                message_data = await self.integration.get_message(parsed["channel"], parsed["ts"])
                if not message_data:
                    raise DescriptionGenerationError("Message not found")

                text_preview = message_data.get("text", "No text")[:80]
                return f"Slack Message: {text_preview}..."

            elif parsed["type"] == "channel":
                channel_info = await self.integration.get_channel_info(parsed["channel"])
                if not channel_info:
                    raise DescriptionGenerationError("Channel not found")

                name = channel_info.get("name", "unknown")
                purpose = channel_info.get("purpose", {}).get("value", "")
                if purpose:
                    return f"Slack Channel #{name}: {purpose}"
                else:
                    return f"Slack Channel #{name}"
            else:
                return f"Slack Resource: {resource_uri}"

        except Exception as e:
            if isinstance(e, ResourceHandlingError | DescriptionGenerationError):
                raise
            logger.error(f"Error generating Slack description for {resource_uri}: {e}")
            raise DescriptionGenerationError(f"Failed to generate Slack description: {e}") from e
