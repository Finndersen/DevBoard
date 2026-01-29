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
    SessionMessage,
    SessionMessageRole,
)
from devboard.agents.events import (
    ConversationEvent,
    MessageRole,
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
            # Skip sidechain messages
            if session_msg.is_sidechain:
                continue

            # Process each content block in the message
            for content_block in session_msg.content:
                block_type = content_block["type"]

                if block_type == "text":
                    # Text content - parse to determine message type
                    text_content: str = content_block["text"]

                    # Parse the message to get its type
                    parsed = ClaudeResponseParser.parse_message_content(text_content)

                    if isinstance(parsed, TextResponse):
                        # Standard text message
                        conv_role = (
                            MessageRole.USER if session_msg.role == SessionMessageRole.USER else MessageRole.AGENT
                        )
                        events.append(
                            TextMessage(
                                role=conv_role,
                                text_content=parsed.content,
                                timestamp=session_msg.timestamp,
                            )
                        )

                    elif isinstance(parsed, VirtualToolCall):
                        # Virtual tool call - convert to ToolCall event (for both invalid and valid calls)
                        # Use helper function to convert to events
                        # Produce a ToolCallRequest if this is the last message in the session, otherwise use ToolCall
                        tool_call_events = convert_virtual_tool_call_to_events(
                            tool_call=parsed,
                            timestamp=session_msg.timestamp,
                            use_tool_call_request=session_idx == message_count - 1,
                        )
                        events.extend(tool_call_events)

                    elif isinstance(parsed, VirtualToolResult):
                        # Tool result - convert to ToolResult event
                        events.append(
                            ToolResult(
                                tool_call_id=parsed.tool_name,  # Use tool_name as ID for virtual tools
                                result_content=parsed.content,
                                is_error=not parsed.successful,
                                timestamp=session_msg.timestamp,
                            )
                        )

                elif block_type == "tool_use":
                    events.append(
                        ToolCall(
                            tool_call_id=content_block["id"],
                            tool_name=content_block["name"],
                            tool_args=content_block["input"],
                            timestamp=session_msg.timestamp,
                        )
                    )

                elif block_type == "tool_result":
                    result_content = content_block["content"]

                    # Convert content to string if it's a list of dicts
                    if isinstance(result_content, list):
                        # Join text blocks from the content
                        text_parts = []
                        for item in result_content:
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
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
