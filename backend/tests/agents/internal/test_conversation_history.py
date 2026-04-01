"""Tests for PydanticAIConversationHistoryService._db_message_to_events."""

import datetime
from unittest.mock import Mock

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_core import to_jsonable_python

from devboard.agents.engines.internal.conversation_history import PydanticAIConversationHistoryService
from devboard.agents.events import MessageRole, TextMessage
from devboard.db.models.messages import MessageType


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
