"""Claude Code conversation history service implementation."""

from datetime import UTC, datetime

import logfire

from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.engines.claude_code.message_parser import (
    ClaudeResponseParser,
    TextResponse,
    VirtualToolCall,
    VirtualToolResult,
    convert_virtual_tool_call_to_events,
)
from devboard.agents.engines.claude_code.session import (
    ClaudeCodeSessionService,
    MetaSessionMessage,
    SessionMessage,
    UserSessionMessage,
)
from devboard.agents.engines.claude_code.utils import normalize_tool_name
from devboard.agents.events import (
    ConversationEvent,
    MessageRole,
    MetaMessage,
    SystemEvent,
    SystemEventType,
    TextMessage,
    ToolCall,
    ToolResult,
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
        return self._session_messages_to_events(session_messages)

    def _session_messages_to_events(self, session_messages: list[SessionMessage]) -> list[ConversationEvent]:
        """Convert session messages to conversation events.

        This method expands each SessionMessage.content list (which can contain multiple blocks)
        into separate events, providing a complete timeline of the conversation including
        tool calls and results.

        Filters out:
        - Sidechain messages
        - Invalid tool calls (malformed JSON that failed validation)

        Args:
            session_messages: List of session messages from Claude Code

        Returns:
            List of ConversationEvent instances (ConversationMessage, ToolCall, ToolResult)
        """
        events: list[ConversationEvent] = []
        message_count = len(session_messages)
        for session_idx, session_msg in enumerate(session_messages):
            if session_msg.is_sidechain:
                continue

            if isinstance(session_msg, MetaSessionMessage):
                events.append(
                    MetaMessage(
                        meta_type=session_msg.meta_type,
                        text_content=session_msg.text_content,
                        timestamp=session_msg.timestamp,
                    )
                )
                continue

            for content_block in session_msg.content:
                if content_block["type"] == "text":
                    parsed = ClaudeResponseParser.parse_message_content(content_block["text"])

                    if isinstance(parsed, TextResponse):
                        conv_role = (
                            MessageRole.USER if isinstance(session_msg, UserSessionMessage) else MessageRole.AGENT
                        )
                        events.append(
                            TextMessage(
                                role=conv_role,
                                text_content=parsed.content,
                                timestamp=session_msg.timestamp,
                            )
                        )

                    elif isinstance(parsed, VirtualToolCall):
                        tool_call_events = convert_virtual_tool_call_to_events(
                            tool_call=parsed,
                            timestamp=session_msg.timestamp,
                            use_tool_call_request=session_idx == message_count - 1,
                        )
                        events.extend(tool_call_events)

                    elif isinstance(parsed, VirtualToolResult):
                        events.append(
                            ToolResult(
                                tool_call_id=parsed.tool_name,
                                result_content=parsed.content,
                                is_error=not parsed.successful,
                                timestamp=session_msg.timestamp,
                            )
                        )

                elif content_block["type"] == "tool_use":
                    events.append(
                        ToolCall(
                            tool_call_id=content_block["id"],
                            tool_name=normalize_tool_name(content_block["name"]),
                            tool_args=content_block["input"],
                            timestamp=session_msg.timestamp,
                        )
                    )

                elif content_block["type"] == "tool_result":
                    result_content = content_block["content"]

                    if isinstance(result_content, list):
                        text_parts = [item.get("text", "") for item in result_content if item.get("type") == "text"]
                        result_str = "\n".join(text_parts)
                    else:
                        result_str = str(result_content)

                    events.append(
                        ToolResult(
                            tool_call_id=content_block["tool_use_id"],
                            result_content=result_str,
                            is_error=content_block.get("is_error", False),
                            timestamp=session_msg.timestamp,
                        )
                    )

        return events
