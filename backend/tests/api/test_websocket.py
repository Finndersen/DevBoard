"""Tests for multiplexed WebSocket conversation event streaming endpoint."""

import asyncio
import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from starlette.websockets import WebSocketDisconnect

from devboard.agents.events import ExecutionCompleteEvent, MessageRole, TextMessage


class TestMultiplexedWebSocket:
    """Tests for the multiplexed /api/ws endpoint."""

    def test_connects_and_receives_event(self, client):
        """WebSocket should deliver tagged events from the broadcast queue."""
        event = TextMessage(
            event_type="message",
            role=MessageRole.AGENT,
            text_content="Hello from agent",
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        broadcast_queue: asyncio.Queue = asyncio.Queue()
        broadcast_queue.put_nowait((42, event))

        mock_mgr = Mock()
        mock_mgr.broadcast_queue = broadcast_queue

        with patch("devboard.api.routers.websocket.get_execution_manager", return_value=mock_mgr):
            with client.websocket_connect("/api/ws") as ws:
                msg = ws.receive_json()
                assert msg["event_type"] == "message"
                assert msg["text_content"] == "Hello from agent"
                assert msg["conversation_id"] == 42

    def test_receives_execution_complete_event_with_conversation_id(self, client):
        """ExecutionCompleteEvent should be tagged with the correct conversation_id."""
        event = ExecutionCompleteEvent(
            status="completed",
            error=None,
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        broadcast_queue: asyncio.Queue = asyncio.Queue()
        broadcast_queue.put_nowait((7, event))

        mock_mgr = Mock()
        mock_mgr.broadcast_queue = broadcast_queue

        with patch("devboard.api.routers.websocket.get_execution_manager", return_value=mock_mgr):
            with client.websocket_connect("/api/ws") as ws:
                msg = ws.receive_json()
                assert msg["event_type"] == "execution_complete"
                assert msg["status"] == "completed"
                assert msg["error"] is None
                assert msg["conversation_id"] == 7

    def test_multiplexes_events_from_multiple_conversations(self, client):
        """Events from different conversations should all arrive tagged with their conversation_id."""
        event_a = TextMessage(
            role=MessageRole.AGENT,
            text_content="From conversation 1",
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        event_b = TextMessage(
            role=MessageRole.AGENT,
            text_content="From conversation 2",
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        broadcast_queue: asyncio.Queue = asyncio.Queue()
        broadcast_queue.put_nowait((1, event_a))
        broadcast_queue.put_nowait((2, event_b))

        mock_mgr = Mock()
        mock_mgr.broadcast_queue = broadcast_queue

        with patch("devboard.api.routers.websocket.get_execution_manager", return_value=mock_mgr):
            with client.websocket_connect("/api/ws") as ws:
                msg_a = ws.receive_json()
                assert msg_a["conversation_id"] == 1
                assert msg_a["text_content"] == "From conversation 1"

                msg_b = ws.receive_json()
                assert msg_b["conversation_id"] == 2
                assert msg_b["text_content"] == "From conversation 2"

    @pytest.mark.asyncio
    async def test_handles_websocket_disconnect_gracefully(self):
        """WebSocketDisconnect should be caught without propagating."""
        broadcast_queue: asyncio.Queue = asyncio.Queue()

        mock_mgr = Mock()
        mock_mgr.broadcast_queue = broadcast_queue

        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock(side_effect=WebSocketDisconnect())

        event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Hello",
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        broadcast_queue.put_nowait((1, event))

        from devboard.api.routers.websocket import multiplexed_websocket

        with patch("devboard.api.routers.websocket.get_execution_manager", return_value=mock_mgr):
            # Should not raise — WebSocketDisconnect is caught internally
            await multiplexed_websocket(mock_websocket)

        mock_websocket.accept.assert_called_once()

    def test_failed_execution_complete_includes_error(self, client):
        """ExecutionCompleteEvent with failed status should include error message."""
        event = ExecutionCompleteEvent(
            status="failed",
            error="Agent crashed unexpectedly",
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        broadcast_queue: asyncio.Queue = asyncio.Queue()
        broadcast_queue.put_nowait((3, event))

        mock_mgr = Mock()
        mock_mgr.broadcast_queue = broadcast_queue

        with patch("devboard.api.routers.websocket.get_execution_manager", return_value=mock_mgr):
            with client.websocket_connect("/api/ws") as ws:
                msg = ws.receive_json()
                assert msg["event_type"] == "execution_complete"
                assert msg["status"] == "failed"
                assert msg["error"] == "Agent crashed unexpectedly"
                assert msg["conversation_id"] == 3

    def test_interrupted_execution_complete_has_no_error(self, client):
        """ExecutionCompleteEvent with interrupted status should have no error."""
        event = ExecutionCompleteEvent(
            status="interrupted",
            error=None,
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        broadcast_queue: asyncio.Queue = asyncio.Queue()
        broadcast_queue.put_nowait((5, event))

        mock_mgr = Mock()
        mock_mgr.broadcast_queue = broadcast_queue

        with patch("devboard.api.routers.websocket.get_execution_manager", return_value=mock_mgr):
            with client.websocket_connect("/api/ws") as ws:
                msg = ws.receive_json()
                assert msg["event_type"] == "execution_complete"
                assert msg["status"] == "interrupted"
                assert msg["error"] is None
                assert msg["conversation_id"] == 5
