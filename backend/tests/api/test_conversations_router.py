"""Tests for conversations API endpoints."""

from unittest.mock import AsyncMock, patch

from devboard.agents.conversation_history import ConversationHistory
from devboard.agents.engines import AgentEngine
from devboard.agents.events import ContextUsage
from devboard.agents.roles import AgentRoleType
from devboard.api.schemas.claude_code_todo import TodoItem, TodoStatus
from devboard.db.models import ParentEntityType


class TestConversationTodosEndpoint:
    """Tests for GET /api/conversations/{id}/todos endpoint."""

    def test_get_todos_returns_empty_for_non_claude_code_engine(self, client, db_session, test_task):
        """Should return empty list for non-Claude Code conversations."""
        from devboard.db.repositories import ConversationRepository

        # Get the internal engine conversation created by test_task fixture
        conv_repo = ConversationRepository(db_session)
        conversation = conv_repo.get_active_conversation_for_entity(
            entity_type=ParentEntityType.TASK,
            entity_id=test_task.id,
        )
        assert conversation is not None
        assert conversation.engine == AgentEngine.INTERNAL

        response = client.get(f"/api/conversations/{conversation.id}/todos")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_todos_returns_empty_for_no_session_id(self, client, db_session, test_task):
        """Should return empty list when no external_session_id is set."""
        from devboard.db.repositories import ConversationRepository

        conv_repo = ConversationRepository(db_session)

        # Create a Claude Code conversation without session ID
        conversation = conv_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=test_task.id,
            agent_role=AgentRoleType.TASK_IMPLEMENTATION,
            engine=AgentEngine.CLAUDE_CODE,
            model_id="anthropic:claude-sonnet-4",
        )
        db_session.commit()

        assert conversation.external_session_id is None

        response = client.get(f"/api/conversations/{conversation.id}/todos")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_todos_returns_empty_when_no_todo_file(self, client, db_session, test_task):
        """Should return empty list when session has no todo file."""
        from devboard.db.repositories import ConversationRepository

        conv_repo = ConversationRepository(db_session)

        # Create a Claude Code conversation with a session ID
        conversation = conv_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=test_task.id,
            agent_role=AgentRoleType.TASK_IMPLEMENTATION,
            engine=AgentEngine.CLAUDE_CODE,
            model_id="anthropic:claude-sonnet-4",
        )
        conv_repo.update_external_session_id(conversation, "test-session-id-123")
        db_session.commit()

        # Mock load_todo_list to raise FileNotFoundError
        with patch("devboard.api.routers.conversations.ClaudeCodeSessionService.load_todo_list") as mock_load:
            mock_load.side_effect = FileNotFoundError("No todo file")

            response = client.get(f"/api/conversations/{conversation.id}/todos")
            assert response.status_code == 200
            assert response.json() == []

    def test_get_todos_returns_todo_list(self, client, db_session, test_task):
        """Should return todo list from session service."""
        from devboard.db.repositories import ConversationRepository

        conv_repo = ConversationRepository(db_session)

        # Create a Claude Code conversation with a session ID
        conversation = conv_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=test_task.id,
            agent_role=AgentRoleType.TASK_IMPLEMENTATION,
            engine=AgentEngine.CLAUDE_CODE,
            model_id="anthropic:claude-sonnet-4",
        )
        conv_repo.update_external_session_id(conversation, "test-session-id-456")
        db_session.commit()

        # Mock the session service to return todos
        mock_todos = [
            TodoItem(
                content="Fix the bug",
                status=TodoStatus.COMPLETED,
                active_form="Fixing the bug",
            ),
            TodoItem(
                content="Write tests",
                status=TodoStatus.IN_PROGRESS,
                active_form="Writing tests",
            ),
            TodoItem(
                content="Update docs",
                status=TodoStatus.PENDING,
                active_form="Updating docs",
            ),
        ]

        with patch("devboard.api.routers.conversations.ClaudeCodeSessionService.load_todo_list") as mock_load:
            mock_load.return_value = mock_todos

            response = client.get(f"/api/conversations/{conversation.id}/todos")
            assert response.status_code == 200

            data = response.json()
            assert len(data) == 3

            assert data[0]["content"] == "Fix the bug"
            assert data[0]["status"] == "completed"
            assert data[0]["active_form"] == "Fixing the bug"

            assert data[1]["content"] == "Write tests"
            assert data[1]["status"] == "in_progress"

            assert data[2]["content"] == "Update docs"
            assert data[2]["status"] == "pending"

    def test_get_todos_returns_404_for_nonexistent_conversation(self, client):
        """Should return 404 for nonexistent conversation."""
        response = client.get("/api/conversations/99999/todos")
        assert response.status_code == 404


class TestGetConversationMessagesEndpoint:
    """Tests for GET /api/conversations/{id}/messages endpoint."""

    def test_returns_messages_and_context_usage(self, client, db_session, test_task):
        """Should return messages list and context_usage in response."""
        from devboard.db.repositories import ConversationRepository

        conv_repo = ConversationRepository(db_session)
        conversation = conv_repo.get_active_conversation_for_entity(
            entity_type=ParentEntityType.TASK,
            entity_id=test_task.id,
        )
        assert conversation is not None

        expected_usage = ContextUsage(
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=800,
            cache_write_tokens=200,
        )

        with (
            patch("devboard.api.dependencies.conversations.create_conversation_history_service") as mock_create_history,
        ):
            mock_service = AsyncMock()
            mock_service.get_conversation_history.return_value = ConversationHistory(
                messages=[], context_usage=expected_usage
            )
            mock_create_history.return_value = mock_service

            response = client.get(f"/api/conversations/{conversation.id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "context_usage" in data
        assert data["messages"] == []
        assert data["context_usage"]["input_tokens"] == 100
        assert data["context_usage"]["output_tokens"] == 50
        assert data["context_usage"]["cache_read_tokens"] == 800
        assert data["context_usage"]["cache_write_tokens"] == 200

    def test_returns_null_context_usage_when_none(self, client, db_session, test_task):
        """Should return null context_usage when no usage data available."""
        from devboard.db.repositories import ConversationRepository

        conv_repo = ConversationRepository(db_session)
        conversation = conv_repo.get_active_conversation_for_entity(
            entity_type=ParentEntityType.TASK,
            entity_id=test_task.id,
        )
        assert conversation is not None

        with patch(
            "devboard.api.dependencies.conversations.create_conversation_history_service"
        ) as mock_create_history:
            mock_service = AsyncMock()
            mock_service.get_conversation_history.return_value = ConversationHistory(messages=[])
            mock_create_history.return_value = mock_service

            response = client.get(f"/api/conversations/{conversation.id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert data["context_usage"] is None


class TestListConversationsEndpoint:
    """Tests for GET /api/conversations/ endpoint."""

    def test_returns_conversations_list(self, client, db_session, test_task):
        """Should return a list of top-level conversations with parent entity names."""
        response = client.get("/api/conversations/")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        # test_task fixture creates conversations for project and task
        assert len(data) >= 1

        # Verify response shape
        item = data[0]
        assert "id" in item
        assert "parent_entity_type" in item
        assert "parent_entity_id" in item
        assert "agent_role" in item
        assert "last_activity_at" in item
        assert "created_at" in item
        assert "parent_entity_name" in item
        assert "project_name" in item

    def test_excludes_completed_task_conversations(self, client, db_session, test_task):
        """Should not include conversations for completed tasks."""
        # Mark the test task as complete
        test_task.status = "complete"
        db_session.commit()

        response = client.get("/api/conversations/")
        assert response.status_code == 200

        data = response.json()
        # The task conversation should be excluded since task is complete
        task_convs = [c for c in data if c["parent_entity_type"] == "TASK" and c["parent_entity_id"] == test_task.id]
        assert len(task_convs) == 0

    def test_returns_empty_list_when_no_conversations(self, client, db_session):
        """Should return empty list when there are no conversations."""
        response = client.get("/api/conversations/")
        assert response.status_code == 200
        assert response.json() == []
