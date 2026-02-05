"""Tests for streaming response utilities."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from devboard.agents.events import ConversationEvent, MessageRole, SystemEvent, SystemEventType, TextMessage
from devboard.api.streaming import cancel_on_disconnect, stream_conversation_events


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = Mock()
    request.receive = AsyncMock()
    return request


async def async_event_generator(*events: ConversationEvent) -> AsyncIterator[ConversationEvent]:
    """Helper to create an async generator from events."""
    for event in events:
        yield event


class TestCancelOnDisconnect:
    """Tests for cancel_on_disconnect context manager."""

    @pytest.mark.asyncio
    async def test_normal_completion_without_disconnect(self, mock_request):
        """Verify context manager completes normally when no disconnect occurs."""
        mock_request.receive = AsyncMock(side_effect=asyncio.CancelledError())

        result = []
        async with cancel_on_disconnect(mock_request):
            result.append("executed")

        assert result == ["executed"]

    @pytest.mark.asyncio
    async def test_cancels_task_on_disconnect(self, mock_request):
        """Verify context manager cancels task when disconnect message received."""
        disconnect_event = asyncio.Event()

        async def mock_receive():
            await disconnect_event.wait()
            return {"type": "http.disconnect"}

        mock_request.receive = mock_receive

        with pytest.raises(asyncio.CancelledError):
            async with cancel_on_disconnect(mock_request):
                disconnect_event.set()
                await asyncio.sleep(0.1)


class TestStreamConversationEvents:
    """Tests for stream_conversation_events function."""

    @pytest.mark.asyncio
    async def test_streams_events_as_ndjson(self, mock_request):
        """Verify events are streamed as newline-delimited JSON."""
        mock_request.receive = AsyncMock(side_effect=asyncio.CancelledError())
        timestamp = datetime.now(UTC)
        events = [
            TextMessage(role=MessageRole.USER, text_content="Hello", timestamp=timestamp),
            TextMessage(role=MessageRole.AGENT, text_content="Hi there", timestamp=timestamp),
        ]

        async def event_gen() -> AsyncIterator[ConversationEvent]:
            for event in events:
                yield event

        response = stream_conversation_events(event_gen(), mock_request)

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        assert len(chunks) == 2
        assert json.loads(chunks[0])["text_content"] == "Hello"
        assert json.loads(chunks[1])["text_content"] == "Hi there"

    @pytest.mark.asyncio
    async def test_closes_generator_on_completion(self, mock_request):
        """Verify async generator is closed after streaming completes."""
        mock_request.receive = AsyncMock(side_effect=asyncio.CancelledError())
        closed = False

        async def event_gen() -> AsyncIterator[ConversationEvent]:
            nonlocal closed
            try:
                yield TextMessage(role=MessageRole.USER, text_content="Test", timestamp=datetime.now(UTC))
            finally:
                closed = True

        response = stream_conversation_events(event_gen(), mock_request)

        async for _ in response.body_iterator:
            pass

        assert closed

    @pytest.mark.asyncio
    async def test_yields_interrupted_event_on_cancellation(self, mock_request):
        """Verify STREAM_INTERRUPTED event is yielded when cancelled."""
        disconnect_event = asyncio.Event()

        async def mock_receive():
            await disconnect_event.wait()
            return {"type": "http.disconnect"}

        mock_request.receive = mock_receive

        async def slow_event_gen() -> AsyncIterator[ConversationEvent]:
            yield TextMessage(role=MessageRole.USER, text_content="First", timestamp=datetime.now(UTC))
            disconnect_event.set()
            await asyncio.sleep(10)
            yield TextMessage(role=MessageRole.USER, text_content="Should not reach", timestamp=datetime.now(UTC))

        response = stream_conversation_events(slow_event_gen(), mock_request)

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        assert len(chunks) == 2
        first_event = json.loads(chunks[0])
        assert first_event["text_content"] == "First"

        last_event = json.loads(chunks[1])
        assert last_event["event_type"] == "system"
        assert last_event["type"] == "stream_interrupted"

    @pytest.mark.asyncio
    async def test_calls_exception_handler_on_error(self, mock_request):
        """Verify exception handler is called when error occurs."""
        mock_request.receive = AsyncMock(side_effect=asyncio.CancelledError())
        error_raised = None

        def exception_handler(e: Exception):
            nonlocal error_raised
            error_raised = e

        async def failing_gen() -> AsyncIterator[ConversationEvent]:
            yield TextMessage(role=MessageRole.USER, text_content="First", timestamp=datetime.now(UTC))
            raise ValueError("Test error")

        response = stream_conversation_events(failing_gen(), mock_request, exception_handler=exception_handler)

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        assert error_raised is not None
        assert isinstance(error_raised, ValueError)
        assert str(error_raised) == "Test error"


class TestStreamInterruptedEventType:
    """Tests for STREAM_INTERRUPTED SystemEventType."""

    def test_stream_interrupted_event_type_exists(self):
        """Verify STREAM_INTERRUPTED is a valid SystemEventType."""
        assert SystemEventType.STREAM_INTERRUPTED == "stream_interrupted"

    def test_can_create_stream_interrupted_event(self):
        """Verify STREAM_INTERRUPTED events can be created."""
        event = SystemEvent(
            type=SystemEventType.STREAM_INTERRUPTED, data={"message": "Test interruption"}, timestamp=datetime.now(UTC)
        )

        assert event.event_type == "system"
        assert event.type == SystemEventType.STREAM_INTERRUPTED
        assert event.data == {"message": "Test interruption"}
