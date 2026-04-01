"""Tests for session_messages_to_events with system_message tag parsing."""

from datetime import UTC, datetime

from devboard.agents.engines.claude_code.session.event_converter import session_messages_to_events
from devboard.agents.engines.claude_code.session.models import (
    AssistantSessionMessage,
    SessionMessage,
    UserSessionMessage,
)
from devboard.agents.events import MessageRole, MetaMessage, MetaMessageType, TextMessage

NOW = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)


def _user_msg(text: str, uuid: str = "uuid-1") -> SessionMessage:
    return UserSessionMessage(
        uuid=uuid,
        timestamp=NOW,
        line_num=1,
        is_sidechain=False,
        content=[{"type": "text", "text": text}],
    )


class TestEventConverterSystemMessageParsing:
    def test_plain_user_message_no_tags(self):
        """User message without system_message tags produces a TextMessage."""
        msgs = [_user_msg("Hello agent")]
        events = session_messages_to_events(msgs)
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.USER
        assert events[0].text_content == "Hello agent"

    def test_user_message_only_system_message_tag(self):
        """User message with only a system_message tag produces only a MetaMessage."""
        text = '<system_message type="initial_context">\nsome context\n</system_message>'
        msgs = [_user_msg(text)]
        events = session_messages_to_events(msgs)
        assert len(events) == 1
        assert isinstance(events[0], MetaMessage)
        assert events[0].meta_type == MetaMessageType.INITIAL_CONTEXT
        assert events[0].text_content == "some context"

    def test_user_message_system_message_tag_with_remaining_text(self):
        """User message with both a tag and remaining text produces MetaMessage + TextMessage."""
        text = '<system_message type="initial_context">\ncontext here\n</system_message>\n\nActual user question'
        msgs = [_user_msg(text)]
        events = session_messages_to_events(msgs)
        assert len(events) == 2
        assert isinstance(events[0], MetaMessage)
        assert events[0].meta_type == MetaMessageType.INITIAL_CONTEXT
        assert events[0].text_content == "context here"
        assert isinstance(events[1], TextMessage)
        assert events[1].role == MessageRole.USER
        assert events[1].text_content == "Actual user question"

    def test_assistant_message_not_parsed_for_system_tags(self):
        """Assistant messages are not parsed for system_message tags (tags treated as plain text)."""
        text = '<system_message type="initial_context">\nsome context\n</system_message>'
        msg: SessionMessage = AssistantSessionMessage(
            uuid="uuid-a",
            timestamp=NOW,
            line_num=1,
            is_sidechain=False,
            content=[{"type": "text", "text": text}],
        )
        events = session_messages_to_events([msg])
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.AGENT
        # Tag text should be preserved as-is for the agent message
        assert "<system_message" in events[0].text_content

    def test_multiple_system_message_tags(self):
        """Multiple system_message tags produce multiple MetaMessages."""
        text = (
            '<system_message type="initial_context">\nfirst\n</system_message>\n'
            '<system_message type="initial_context">\nsecond\n</system_message>'
        )
        msgs = [_user_msg(text)]
        events = session_messages_to_events(msgs)
        assert len(events) == 2
        assert isinstance(events[0], MetaMessage)
        assert isinstance(events[1], MetaMessage)
        assert events[0].text_content == "first"
        assert events[1].text_content == "second"

    def test_uuid_preserved_on_meta_message(self):
        """MetaMessage inherits the uuid from the session message."""
        text = '<system_message type="initial_context">\nctx\n</system_message>'
        msgs = [_user_msg(text, uuid="my-uuid-123")]
        events = session_messages_to_events(msgs)
        assert isinstance(events[0], MetaMessage)
        assert events[0].uuid == "my-uuid-123"
