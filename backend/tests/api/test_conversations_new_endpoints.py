"""Tests for new conversation API endpoints (POST /messages, POST /approve-tools, POST /interrupt)."""

from unittest.mock import Mock, patch

from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution_manager import ConversationExecution
from devboard.db.models import ParentEntityType
from devboard.db.models.task import TaskStatus
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


class TestSendConversationMessage:
    """Tests for POST /api/conversations/{id}/messages."""

    def test_returns_conversation_id_on_success(self, client, db_session, test_task):
        """Should start background execution and return conversation_id."""
        conversation = _get_task_conversation(db_session, test_task)

        with patch("devboard.api.routers.conversations.conversation_execution_manager") as mock_mgr:
            mock_mgr.start_agent_execution.return_value = Mock(spec=ConversationExecution)

            response = client.post(
                f"/api/conversations/{conversation.id}/messages",
                json={"message": "Hello, agent!"},
            )

        assert response.status_code == 200
        assert response.json() == {"conversation_id": conversation.id}
        mock_mgr.start_agent_execution.assert_called_once()

    def test_returns_409_when_execution_already_active(self, client, db_session, test_task):
        """Should return 409 Conflict if an execution is already running."""
        conversation = _get_task_conversation(db_session, test_task)

        with patch("devboard.api.routers.conversations.conversation_execution_manager") as mock_mgr:
            mock_mgr.start_agent_execution.side_effect = ConversationBusyError(conversation.id)

            response = client.post(
                f"/api/conversations/{conversation.id}/messages",
                json={"message": "Hello, agent!"},
            )

        assert response.status_code == 409
        assert "already active" in response.json()["detail"].lower()

    def test_returns_400_for_completed_task(self, client, db_session, test_task):
        """Should return 400 when conversation belongs to a completed task."""
        # Mark the task as complete
        test_task.status = TaskStatus.COMPLETE
        db_session.commit()

        conversation = _get_task_conversation(db_session, test_task)

        try:
            response = client.post(
                f"/api/conversations/{conversation.id}/messages",
                json={"message": "Hello!"},
            )
            assert response.status_code == 400
            assert "completed" in response.json()["detail"].lower()
        finally:
            # Restore task status
            test_task.status = TaskStatus.PLANNING
            db_session.commit()

    def test_returns_404_for_nonexistent_conversation(self, client):
        """Should return 404 for a nonexistent conversation."""
        response = client.post(
            "/api/conversations/99999/messages",
            json={"message": "Hello!"},
        )
        assert response.status_code == 404


class TestApproveConversationTools:
    """Tests for POST /api/conversations/{id}/approve-tools."""

    def test_returns_conversation_id_on_success(self, client, db_session, test_task):
        """Should start background execution with approvals and return conversation_id."""
        conversation = _get_task_conversation(db_session, test_task)

        with patch("devboard.api.routers.conversations.conversation_execution_manager") as mock_mgr:
            mock_mgr.start_agent_execution.return_value = Mock(spec=ConversationExecution)

            response = client.post(
                f"/api/conversations/{conversation.id}/approve-tools",
                json={"approvals": {}},
            )

        assert response.status_code == 200
        assert response.json() == {"conversation_id": conversation.id}
        mock_mgr.start_agent_execution.assert_called_once()

    def test_returns_409_when_execution_already_active(self, client, db_session, test_task):
        """Should return 409 Conflict if an execution is already running."""
        conversation = _get_task_conversation(db_session, test_task)

        with patch("devboard.api.routers.conversations.conversation_execution_manager") as mock_mgr:
            mock_mgr.start_agent_execution.side_effect = ConversationBusyError(conversation.id)

            response = client.post(
                f"/api/conversations/{conversation.id}/approve-tools",
                json={"approvals": {}},
            )

        assert response.status_code == 409

    def test_returns_404_for_nonexistent_conversation(self, client):
        """Should return 404 for a nonexistent conversation."""
        response = client.post(
            "/api/conversations/99999/approve-tools",
            json={"approvals": {}},
        )
        assert response.status_code == 404


class TestInterruptConversation:
    """Tests for POST /api/conversations/{id}/interrupt."""

    def test_returns_200_when_execution_interrupted(self, client, db_session, test_task):
        """Should return 200 and interrupt_requested status when execution is active."""
        conversation = _get_task_conversation(db_session, test_task)

        with patch("devboard.api.routers.conversations.conversation_execution_manager") as mock_mgr:
            mock_mgr.request_interrupt.return_value = True

            response = client.post(f"/api/conversations/{conversation.id}/interrupt")

        assert response.status_code == 200
        assert response.json() == {"status": "interrupt_requested"}
        mock_mgr.request_interrupt.assert_called_once_with(conversation.id)

    def test_returns_404_when_no_active_execution(self, client, db_session, test_task):
        """Should return 404 when no active execution exists."""
        conversation = _get_task_conversation(db_session, test_task)

        with patch("devboard.api.routers.conversations.conversation_execution_manager") as mock_mgr:
            mock_mgr.request_interrupt.return_value = False

            response = client.post(f"/api/conversations/{conversation.id}/interrupt")

        assert response.status_code == 404

    def test_returns_404_for_nonexistent_conversation(self, client):
        """Should return 404 for a nonexistent conversation."""
        response = client.post("/api/conversations/99999/interrupt")
        assert response.status_code == 404
