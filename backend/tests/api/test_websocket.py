"""Tests for WebSocket conversation event streaming endpoint."""

import asyncio
import datetime
from unittest.mock import Mock, patch

import pytest
from starlette.websockets import WebSocketDisconnect

from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.execution_manager import (
    ConversationExecution,
    ExecutionLifecycleEventType,
    ExecutionStatus,
)
from devboard.db.models import ParentEntityType
from devboard.db.repositories import ConversationRepository


def _get_task_conversation(db_session, test_task):
    """Helper to get the task's conversation from the test fixture."""
    conv_repo = ConversationRepository(db_session)
    conversation = conv_repo.get_active_conversation_for_entity(
        entity_type=ParentEntityType.TASK,
        entity_id=test_task.id,
    )
    assert conversation is not None
    return conversation


def _make_execution(
    conversation_id: int = 1,
    status: ExecutionStatus = ExecutionStatus.RUNNING,
) -> ConversationExecution:
    """Create a mock ConversationExecution for testing."""
    queue: asyncio.Queue = asyncio.Queue()
    return ConversationExecution(
        conversation_id=conversation_id,
        event_queue=queue,
        interrupt_requested=asyncio.Event(),
        asyncio_task=Mock(),
        status=status,
        started_at=datetime.datetime.now(datetime.UTC),
    )


class TestWebSocketConnectionLifecycle:
    """Tests for WebSocket connection establishment and teardown."""

    def test_closes_with_4004_for_nonexistent_conversation(self, client):
        """WebSocket should close with code 4004 when conversation not found."""
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/conversations/99999/ws") as ws:
                ws.receive_json()
        assert exc_info.value.code == 4004

    def test_connects_successfully_for_valid_conversation(self, client, db_session, test_task):
        """WebSocket should connect successfully for a valid conversation."""
        conversation = _get_task_conversation(db_session, test_task)

        # Mock the execution manager to never return an execution — WS stays idle
        with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
            mock_mgr.get_execution.return_value = None

            with client.websocket_connect(f"/api/conversations/{conversation.id}/ws") as ws:
                # Connection should be accepted (no immediate close)
                # We can't easily test the idle polling loop, so just verify
                # the connection was accepted without 4004
                assert ws is not None


class TestWebSocketEventStreaming:
    """Tests for event delivery through WebSocket."""

    def test_sends_execution_started_and_completed_events(self, client, db_session, test_task):
        """Should send execution_started, then execution_completed lifecycle events."""
        conversation = _get_task_conversation(db_session, test_task)

        execution = _make_execution(conversation.id)

        # Pre-populate the queue with sentinel to simulate immediate completion
        execution.event_queue.put_nowait(None)
        execution.status = ExecutionStatus.COMPLETED

        # Simulate that get_execution returns the execution on first call,
        # then None afterward to stop the loop
        call_count = 0

        def get_execution_side_effect(_conv_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return execution
            return None

        with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
            mock_mgr.get_execution.side_effect = get_execution_side_effect

            with client.websocket_connect(f"/api/conversations/{conversation.id}/ws") as ws:
                # Receive execution_started
                started_msg = ws.receive_json()
                assert started_msg["event_type"] == "execution_lifecycle"
                assert started_msg["event"] == ExecutionLifecycleEventType.EXECUTION_STARTED

                # Receive execution_completed
                completed_msg = ws.receive_json()
                assert completed_msg["event_type"] == "execution_lifecycle"
                assert completed_msg["event"] == ExecutionLifecycleEventType.EXECUTION_COMPLETED
                assert completed_msg["status"] == ExecutionStatus.COMPLETED

    def test_sends_conversation_events_before_completion(self, client, db_session, test_task):
        """Should send ConversationEvent objects before the completion event."""
        conversation = _get_task_conversation(db_session, test_task)

        execution = _make_execution(conversation.id)

        # Add a text message event and sentinel to the queue
        text_event = TextMessage(
            event_type="message",
            role=MessageRole.AGENT,
            text_content="Hello from agent",
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        execution.event_queue.put_nowait(text_event)
        execution.event_queue.put_nowait(None)  # sentinel
        execution.status = ExecutionStatus.COMPLETED

        call_count = 0

        def get_execution_side_effect(_conv_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return execution
            return None

        with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
            mock_mgr.get_execution.side_effect = get_execution_side_effect

            with client.websocket_connect(f"/api/conversations/{conversation.id}/ws") as ws:
                # execution_started
                started_msg = ws.receive_json()
                assert started_msg["event_type"] == "execution_lifecycle"
                assert started_msg["event"] == "execution_started"

                # conversation event
                event_msg = ws.receive_json()
                assert event_msg["event_type"] == "message"
                assert event_msg["text_content"] == "Hello from agent"

                # execution_completed
                completed_msg = ws.receive_json()
                assert completed_msg["event_type"] == "execution_lifecycle"
                assert completed_msg["event"] == "execution_completed"
                assert completed_msg["status"] == "completed"

    def test_sends_failed_status_when_execution_fails(self, client, db_session, test_task):
        """Should include error message in execution_completed when status is FAILED."""
        conversation = _get_task_conversation(db_session, test_task)

        execution = _make_execution(conversation.id)
        execution.event_queue.put_nowait(None)
        execution.status = ExecutionStatus.FAILED
        execution.error = "Agent crashed"

        call_count = 0

        def get_execution_side_effect(_conv_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return execution
            return None

        with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
            mock_mgr.get_execution.side_effect = get_execution_side_effect

            with client.websocket_connect(f"/api/conversations/{conversation.id}/ws") as ws:
                ws.receive_json()  # execution_started

                completed_msg = ws.receive_json()
                assert completed_msg["event_type"] == "execution_lifecycle"
                assert completed_msg["status"] == "failed"
                assert completed_msg["error"] == "Agent crashed"

    def test_sends_interrupted_status_when_execution_interrupted(self, client, db_session, test_task):
        """Should send interrupted status in execution_completed when agent was interrupted."""
        conversation = _get_task_conversation(db_session, test_task)

        execution = _make_execution(conversation.id)
        execution.event_queue.put_nowait(None)
        execution.status = ExecutionStatus.INTERRUPTED

        call_count = 0

        def get_execution_side_effect(_conv_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return execution
            return None

        with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
            mock_mgr.get_execution.side_effect = get_execution_side_effect

            with client.websocket_connect(f"/api/conversations/{conversation.id}/ws") as ws:
                ws.receive_json()  # execution_started

                completed_msg = ws.receive_json()
                assert completed_msg["status"] == "interrupted"
                assert completed_msg["error"] is None
