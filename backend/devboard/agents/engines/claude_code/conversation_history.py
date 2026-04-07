"""Claude Code conversation history service implementation."""

from datetime import UTC, datetime

import logfire

from devboard.agents.conversation_history import ConversationHistory, ConversationHistoryService
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionService, SessionMessage
from devboard.agents.engines.claude_code.session.event_converter import session_messages_to_events
from devboard.agents.engines.claude_code.session.models import AssistantSessionMessage
from devboard.agents.events import (
    ContextUsage,
    SystemEvent,
    SystemEventType,
)


class ClaudeCodeConversationHistoryService(ConversationHistoryService):
    """Service for retrieving conversation history from Claude Code sessions.

    This service retrieves messages from Claude Code session files and converts them
    to ConversationEvent format for display.

    Note: Claude Code manages its own session files. This service reads from
    session files as needed rather than storing messages in the database.
    """

    @property
    def session_id(self) -> str | None:
        return self.conversation.external_session_id

    async def get_conversation_history(self) -> ConversationHistory:
        if not self.session_id:
            return ConversationHistory()

        claude_session_service = ClaudeCodeSessionService()
        try:
            session_messages = claude_session_service.load_session_messages(self.session_id)
        except FileNotFoundError:
            logfire.warn(f"Session file not found for conversation {self.conversation.id}, session ID preserved")
            return ConversationHistory(
                messages=[
                    SystemEvent(
                        type=SystemEventType.SESSION_EXPIRED,
                        data={
                            "message": "Claude Code session file not found. Clear this conversation to start a new one."
                        },
                        timestamp=datetime.now(UTC),
                    )
                ]
            )

        events = session_messages_to_events(session_messages)
        context_usage = self._extract_usage(session_messages)
        return ConversationHistory(messages=events, context_usage=context_usage)

    @staticmethod
    def _extract_usage(session_messages: list[SessionMessage]) -> ContextUsage | None:
        """Extract context usage from the last AssistantSessionMessage with usage data."""
        for msg in reversed(session_messages):
            if isinstance(msg, AssistantSessionMessage) and msg.usage:
                usage = msg.usage
                return ContextUsage(
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                    cache_write_tokens=usage.get("cache_creation_input_tokens", 0),
                )
        return None
