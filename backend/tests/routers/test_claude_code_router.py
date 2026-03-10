"""Tests for Claude Code session viewer router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import ConversationRepository, DocumentRepository, ProjectRepository, TaskRepository


@pytest.fixture
def test_task(db_session, test_codebase):
    """Create a test task for linking to sessions."""
    document_repo = DocumentRepository(db_session)
    project_repo = ProjectRepository(db_session)
    task_repo = TaskRepository(db_session)

    spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
    project = project_repo.create(name="Test Project", description="", specification=spec_doc)
    task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
    task = task_repo.create(
        project_id=project.id,
        title="Test Task",
        status=TaskStatus.PLANNING,
        specification=task_spec_doc,
        base_branch="main",
        branch_name="",
        codebase_id=test_codebase.id,
    )
    db_session.flush()
    return task


def _make_session_info(session_id: str):
    """Create a mock ClaudeCodeSessionInfo dataclass instance."""
    from devboard.agents.engines.claude_code.session.manager import ClaudeCodeSessionInfo

    return ClaudeCodeSessionInfo(
        session_id=session_id,
        label=f"Session {session_id}",
        last_activity=datetime(2026, 3, 7, 12, 0, 0, tzinfo=UTC),
        file_size=1024,
        is_empty=False,
        linked_session_id=None,
        session_role=None,
    )


class TestListSessionsEndpoint:
    """Tests for GET /api/claude-code/projects/{encoded_project_path}/sessions."""

    def test_returns_sessions_without_task_info_when_no_conversations(self, client):
        """Sessions with no matching conversations return task_info=null."""
        mock_sessions = [_make_session_info("session-abc")]

        with patch(
            "devboard.api.routers.claude_code.ClaudeSessionManager.list_sessions",
            new=AsyncMock(return_value=mock_sessions),
        ):
            response = client.get("/api/claude-code/projects/test-project/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["session_id"] == "session-abc"
        assert data[0]["task_info"] is None

    def test_returns_task_info_for_linked_session(self, client, db_session, test_task):
        """Sessions linked to a task conversation include task_info."""
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=test_task.id,
            agent_role=AgentRoleType.TASK_PLANNING,
            engine=AgentEngine.INTERNAL,
            model_id=None,
            external_session_id="linked-session",
        )
        db_session.flush()

        mock_sessions = [_make_session_info("linked-session"), _make_session_info("unlinked-session")]

        with patch(
            "devboard.api.routers.claude_code.ClaudeSessionManager.list_sessions",
            new=AsyncMock(return_value=mock_sessions),
        ):
            response = client.get("/api/claude-code/projects/test-project/sessions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        linked = next(s for s in data if s["session_id"] == "linked-session")
        assert linked["task_info"] == {
            "task_id": test_task.id,
            "task_title": "Test Task",
            "agent_role": "task_planning",
        }

        unlinked = next(s for s in data if s["session_id"] == "unlinked-session")
        assert unlinked["task_info"] is None

    def test_returns_404_when_project_not_found(self, client):
        """Returns 404 when the project directory does not exist."""
        with patch(
            "devboard.api.routers.claude_code.ClaudeSessionManager.list_sessions",
            new=AsyncMock(side_effect=FileNotFoundError("Project not found")),
        ):
            response = client.get("/api/claude-code/projects/nonexistent/sessions")

        assert response.status_code == 404


class TestLocateSessionEndpoint:
    """Tests for GET /api/claude-code/sessions/{session_id}/locate."""

    def test_returns_project_encoded_path_for_found_session(self, client):
        """Returns 200 with project_encoded_path when session exists."""
        with patch(
            "devboard.api.routers.claude_code.ClaudeSessionManager.locate_session",
            new=Mock(return_value="-Users-foo-myproject"),
        ):
            response = client.get("/api/claude-code/sessions/sess-abc/locate")

        assert response.status_code == 200
        assert response.json() == {"project_encoded_path": "-Users-foo-myproject"}

    def test_returns_404_when_session_not_found(self, client):
        """Returns 404 when session file cannot be found."""
        with patch(
            "devboard.api.routers.claude_code.ClaudeSessionManager.locate_session",
            new=Mock(side_effect=FileNotFoundError("Session not found")),
        ):
            response = client.get("/api/claude-code/sessions/nonexistent/locate")

        assert response.status_code == 404
