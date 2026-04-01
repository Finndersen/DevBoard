"""Tests for PydanticAIConversationHistoryService."""

import datetime
from unittest.mock import MagicMock, Mock

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_core import to_jsonable_python

from devboard.agents.engines.internal.conversation_history import PydanticAIConversationHistoryService
from devboard.agents.events import MessageRole, MetaMessage, MetaMessageType, TextMessage
from devboard.db.models.messages import ConversationMessage, MessageType

NOW = datetime.datetime(2025, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)


def _make_history_service() -> PydanticAIConversationHistoryService:
    """Create a PydanticAIConversationHistoryService with mock dependencies."""
    service = PydanticAIConversationHistoryService.__new__(PydanticAIConversationHistoryService)
    service.conversation = Mock()
    service.conversation_repo = Mock()
    return service


def _make_text_response_msg(text: str, model_name: str | None = None) -> Mock:
    """Create a mock DbConversationMessage for a TEXT_RESPONSE type."""
    model_response = ModelResponse(
        parts=[TextPart(content=text)],
        model_name=model_name,
    )
    msg = Mock()
    msg.message_type = MessageType.TEXT_RESPONSE
    msg.text_content = text
    msg.timestamp = datetime.datetime(2025, 10, 8, 15, 0, 0, tzinfo=datetime.UTC)
    msg.pydantic_content = to_jsonable_python(model_response)
    return msg


def _user_prompt_msg(text: str) -> ConversationMessage:
    msg = MagicMock(spec=ConversationMessage)
    msg.message_type = MessageType.USER_PROMPT
    msg.text_content = text
    msg.timestamp = NOW
    return msg


class TestDbMessageToEventsModel:
    """Tests for model_name extraction in _db_message_to_events."""

    def test_text_response_with_model_name(self):
        """model_name from ModelResponse pydantic_content is set on TextMessage.model."""
        service = _make_history_service()
        msg = _make_text_response_msg("Hello world", model_name="claude-sonnet-4-20250514")

        events = service._db_message_to_events(msg)

        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.AGENT
        assert events[0].text_content == "Hello world"
        assert events[0].model == "claude-sonnet-4-20250514"

    def test_text_response_without_model_name(self):
        """TextMessage.model is None when ModelResponse has no model_name."""
        service = _make_history_service()
        msg = _make_text_response_msg("Hello world", model_name=None)

        events = service._db_message_to_events(msg)

        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].model is None

    def test_user_prompt_has_no_model(self):
        """User prompt TextMessage always has model=None."""
        service = _make_history_service()
        msg = Mock()
        msg.message_type = MessageType.USER_PROMPT
        msg.text_content = "User question"
        msg.timestamp = datetime.datetime(2025, 10, 8, 15, 0, 0, tzinfo=datetime.UTC)

        events = service._db_message_to_events(msg)

        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.USER
        assert events[0].model is None


class TestPydanticAIConversationHistoryServiceSystemMessageParsing:
    """Tests for _db_message_to_events with system_message tag parsing."""

    def _service(self) -> PydanticAIConversationHistoryService:
        """Create a minimal service instance without DB dependencies."""
        service = PydanticAIConversationHistoryService.__new__(PydanticAIConversationHistoryService)
        return service

    def test_plain_user_message_no_tags(self):
        """User message without system_message tags produces a TextMessage."""
        service = self._service()
        msg = _user_prompt_msg("Hello agent")
        events = service._db_message_to_events(msg)
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.USER
        assert events[0].text_content == "Hello agent"

    def test_user_message_only_system_message_tag(self):
        """User message with only a system_message tag produces only a MetaMessage."""
        service = self._service()
        text = '<system_message type="initial_context">\nsome context\n</system_message>'
        msg = _user_prompt_msg(text)
        events = service._db_message_to_events(msg)
        assert len(events) == 1
        assert isinstance(events[0], MetaMessage)
        assert events[0].meta_type == MetaMessageType.INITIAL_CONTEXT
        assert events[0].text_content == "some context"

    def test_user_message_system_message_tag_with_remaining_text(self):
        """User message with both a tag and remaining text produces MetaMessage + TextMessage."""
        service = self._service()
        text = '<system_message type="initial_context">\ncontext here\n</system_message>\n\nActual user question'
        msg = _user_prompt_msg(text)
        events = service._db_message_to_events(msg)
        assert len(events) == 2
        assert isinstance(events[0], MetaMessage)
        assert events[0].meta_type == MetaMessageType.INITIAL_CONTEXT
        assert events[0].text_content == "context here"
        assert isinstance(events[1], TextMessage)
        assert events[1].role == MessageRole.USER
        assert events[1].text_content == "Actual user question"

    def test_user_message_multiple_system_message_tags(self):
        """Multiple system_message tags produce multiple MetaMessages."""
        service = self._service()
        text = (
            '<system_message type="initial_context">\nfirst\n</system_message>\n'
            '<system_message type="initial_context">\nsecond\n</system_message>'
        )
        msg = _user_prompt_msg(text)
        events = service._db_message_to_events(msg)
        assert len(events) == 2
        assert isinstance(events[0], MetaMessage)
        assert isinstance(events[1], MetaMessage)
        assert events[0].text_content == "first"
        assert events[1].text_content == "second"

    def test_empty_remaining_text_not_added(self):
        """If only system_message tags and no remaining text, no TextMessage is added."""
        service = self._service()
        text = '<system_message type="initial_context">\nctx\n</system_message>'
        msg = _user_prompt_msg(text)
        events = service._db_message_to_events(msg)
        assert len(events) == 1
        assert isinstance(events[0], MetaMessage)
