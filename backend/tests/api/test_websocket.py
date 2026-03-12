"""Tests for WebSocket conversation event streaming endpoint."""

import asyncio
import datetime
from contextlib import contextmanager
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


@contextmanager
def _patch_websocket_session(db_session):
    """Patch SessionLocal in websocket module to return the test DB session.

    The websocket handler creates a short-lived SessionLocal() for validation.
    In tests, we need it to see the test fixture data, so we redirect to the
    test session (which is NOT closed by the handler since we control its lifecycle).
    """
    mock_session_local = Mock(return_value=db_session)
    with patch("devboard.api.routers.websocket.SessionLocal", mock_session_local):
        yield


class TestWebSocketConnectionLifecycle:
    """Tests for WebSocket connection establishment and teardown."""

    def test_closes_with_4004_for_nonexistent_conversation(self, client, db_session):
        """WebSocket should close with code 4004 when conversation not found."""
        with _patch_websocket_session(db_session):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/api/conversations/99999/ws") as ws:
                    ws.receive_json()
            assert exc_info.value.code == 4004

    def test_connects_successfully_for_valid_conversation(self, client, db_session, test_task):
        """WebSocket should connect successfully for a valid conversation."""
        conversation = _get_task_conversation(db_session, test_task)

        with _patch_websocket_session(db_session):
            with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
                mock_mgr.get_execution.return_value = None

                with client.websocket_connect(f"/api/conversations/{conversation.id}/ws") as ws:
                    # Connection should be accepted (no immediate close)
                    assert ws is not None


class TestWebSocketEventStreaming:
    """Tests for event delivery through WebSocket."""

    def test_sends_execution_started_and_completed_events(self, client, db_session, test_task):
        """Should send execution_started, then execution_completed lifecycle events."""
        conversation = _get_task_conversation(db_session, test_task)

        # Mirrors real ExecutionManager: status is set BEFORE sentinel is pushed
        execution = _make_execution(conversation.id)
        execution.status = ExecutionStatus.COMPLETED
        execution.event_queue.put_nowait(None)  # sentinel

        with _patch_websocket_session(db_session):
            with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
                mock_mgr.get_execution.return_value = execution

                with pytest.raises(WebSocketDisconnect) as exc_info:
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

                        # Server closes the WebSocket — next receive triggers disconnect
                        ws.receive_json()

                assert exc_info.value.code == 1000

    def test_sends_conversation_events_before_completion(self, client, db_session, test_task):
        """Should send ConversationEvent objects before the completion event."""
        conversation = _get_task_conversation(db_session, test_task)

        execution = _make_execution(conversation.id)

        text_event = TextMessage(
            event_type="message",
            role=MessageRole.AGENT,
            text_content="Hello from agent",
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        execution.event_queue.put_nowait(text_event)
        # Mirrors real ExecutionManager: status is set BEFORE sentinel
        execution.status = ExecutionStatus.COMPLETED
        execution.event_queue.put_nowait(None)  # sentinel

        with _patch_websocket_session(db_session):
            with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
                mock_mgr.get_execution.return_value = execution

                with pytest.raises(WebSocketDisconnect) as exc_info:
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

                        # Server closes the WebSocket
                        ws.receive_json()

                assert exc_info.value.code == 1000

    def test_sends_failed_status_when_execution_fails(self, client, db_session, test_task):
        """Should include error message in execution_completed when status is FAILED."""
        conversation = _get_task_conversation(db_session, test_task)

        execution = _make_execution(conversation.id)
        # Mirrors real ExecutionManager: status and error set BEFORE sentinel
        execution.status = ExecutionStatus.FAILED
        execution.error = "Agent crashed"
        execution.event_queue.put_nowait(None)

        with _patch_websocket_session(db_session):
            with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
                mock_mgr.get_execution.return_value = execution

                with pytest.raises(WebSocketDisconnect) as exc_info:
                    with client.websocket_connect(f"/api/conversations/{conversation.id}/ws") as ws:
                        ws.receive_json()  # execution_started

                        completed_msg = ws.receive_json()
                        assert completed_msg["event_type"] == "execution_lifecycle"
                        assert completed_msg["status"] == "failed"
                        assert completed_msg["error"] == "Agent crashed"

                        ws.receive_json()  # triggers server close

                assert exc_info.value.code == 1000

    def test_sends_interrupted_status_when_execution_interrupted(self, client, db_session, test_task):
        """Should send interrupted status in execution_completed when agent was interrupted."""
        conversation = _get_task_conversation(db_session, test_task)

        execution = _make_execution(conversation.id)
        # Mirrors real ExecutionManager: status set BEFORE sentinel
        execution.status = ExecutionStatus.INTERRUPTED
        execution.event_queue.put_nowait(None)

        with _patch_websocket_session(db_session):
            with patch("devboard.api.routers.websocket.conversation_execution_manager") as mock_mgr:
                mock_mgr.get_execution.return_value = execution

                with pytest.raises(WebSocketDisconnect) as exc_info:
                    with client.websocket_connect(f"/api/conversations/{conversation.id}/ws") as ws:
                        ws.receive_json()  # execution_started

                        completed_msg = ws.receive_json()
                        assert completed_msg["status"] == "interrupted"
                        assert completed_msg["error"] is None

                        ws.receive_json()  # triggers server close

                assert exc_info.value.code == 1000
