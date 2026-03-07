"""Claude Code conversation history service implementation."""

from datetime import UTC, datetime

import logfire

from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionService
from devboard.agents.engines.claude_code.session.event_converter import session_messages_to_events
from devboard.agents.events import (
    ConversationEvent,
    SystemEvent,
    SystemEventType,
)


class ClaudeCodeConversationHistoryService(ConversationHistoryService):
    """Service for retrieving conversation history from Claude Code sessions.

    This service retrieves messages from Claude Code session files and converts them
    to ConversationEvent format for display.

    Note: Claude Code manages its own session files. This service reads from
    session files as needed rather than storing messages in the database.

    Attributes:
        conversation: The conversation instance (from base class)
        conversation_repo: Repository for conversation operations
    """

    @property
    def session_id(self) -> str | None:
        """Get the current Claude session ID from the conversation."""
        return self.conversation.external_session_id

    async def get_conversation_messages(self) -> list[ConversationEvent]:
        """Retrieve all events for the Claude Code conversation.

        Events are loaded from Claude Code session files and include text messages,
        tool calls, and tool results in chronological order.
        Claude Code manages its own session storage in ~/.claude/projects.

        Returns:
            List of ConversationEvent instances in chronological order.
            Returns empty list if no session_id (conversation hasn't started or was cleared).
            Returns a SESSION_EXPIRED event if the session file was cleaned up.
        """
        # Return empty list if no session exists yet
        if not self.session_id:
            return []

        # Load low-level session messages
        claude_session_service = ClaudeCodeSessionService()
        try:
            session_messages = claude_session_service.load_session_messages(self.session_id)
        except FileNotFoundError:
            # Session file was cleaned up - reset session ID and return warning
            logfire.info(f"Session file not found for conversation {self.conversation.id}, resetting session ID")
            self.conversation_repo.update_external_session_id(self.conversation, None)
            self.conversation_repo.commit()
            return [
                SystemEvent(
                    type=SystemEventType.SESSION_EXPIRED,
                    data={"message": "Claude session was cleaned up, starting new conversation"},
                    timestamp=datetime.now(UTC),
                )
            ]

        # Convert to conversation events with filtering
        return session_messages_to_events(session_messages)
