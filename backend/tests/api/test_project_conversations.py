"""Tests for project conversation API endpoints and conversation PATCH/DELETE endpoints."""

import pytest

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.repositories import ConversationRepository, DocumentRepository, ProjectRepository


@pytest.fixture
def project_with_conversation(db_session):
    """Create a project with an initial conversation."""
    document_repo = DocumentRepository(db_session)
    project_repo = ProjectRepository(db_session)
    conversation_repo = ConversationRepository(db_session)

    spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
    project = project_repo.create(
        name="Test Project",
        description="A project for testing conversations",
        specification=spec_doc,
    )
    db_session.flush()

    conversation = conversation_repo.create(
        parent_entity_type=ParentEntityType.PROJECT,
        parent_entity_id=project.id,
        agent_role=AgentRoleType.PROJECT,
        engine=AgentEngine.INTERNAL,
        model_id="openai:gpt-4",
    )
    db_session.commit()

    return project, conversation


class TestListProjectConversations:
    """Tests for GET /api/projects/{id}/conversations."""

    def test_returns_conversations_list(self, client, db_session, project_with_conversation):
        project, conversation = project_with_conversation

        response = client.get(f"/api/projects/{project.id}/conversations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        conv_ids = [c["id"] for c in data]
        assert conversation.id in conv_ids

        matching = [c for c in data if c["id"] == conversation.id][0]
        assert matching["parent_entity_type"] == "project"
        assert matching["parent_entity_id"] == project.id
        assert matching["agent_role"] == "project"
        assert matching["parent_entity_name"] == "Test Project"

    def test_returns_empty_for_project_with_no_conversations(self, client, db_session):
        """Returns empty list for project with no conversations."""
        document_repo = DocumentRepository(db_session)
        project_repo = ProjectRepository(db_session)

        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(
            name="Empty Project",
            description="",
            specification=spec_doc,
        )
        db_session.commit()

        response = client.get(f"/api/projects/{project.id}/conversations")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_404_for_nonexistent_project(self, client):
        response = client.get("/api/projects/99999/conversations")
        assert response.status_code == 404

    def test_excludes_archived_conversations(self, client, db_session, project_with_conversation):
        project, conversation = project_with_conversation

        # Archive the conversation
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.archive_conversation(conversation.id)
        db_session.commit()

        response = client.get(f"/api/projects/{project.id}/conversations")

        assert response.status_code == 200
        conv_ids = [c["id"] for c in response.json()]
        assert conversation.id not in conv_ids


class TestCreateProjectConversation:
    """Tests for POST /api/projects/{id}/conversations."""

    def test_creates_conversation(self, client, db_session, project_with_conversation):
        project, _ = project_with_conversation

        response = client.post(f"/api/projects/{project.id}/conversations")

        assert response.status_code == 200
        data = response.json()
        assert data["parent_entity_type"] == "project"
        assert data["parent_entity_id"] == project.id
        assert data["agent_role"] == "project"
        assert data["is_active"] is True
        assert "id" in data
        assert "at_cap" in data

    def test_returns_at_cap_false_when_under_cap(self, client, db_session, project_with_conversation):
        project, _ = project_with_conversation

        response = client.post(f"/api/projects/{project.id}/conversations")

        assert response.status_code == 200
        assert response.json()["at_cap"] is False

    def test_returns_404_for_nonexistent_project(self, client):
        response = client.post("/api/projects/99999/conversations")
        assert response.status_code == 404


class TestUpdateConversation:
    """Tests for PATCH /api/conversations/{id}."""

    def test_renames_conversation(self, client, db_session, project_with_conversation):
        _, conversation = project_with_conversation

        response = client.patch(
            f"/api/conversations/{conversation.id}",
            json={"title": "New Conversation Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Conversation Title"
        assert data["id"] == conversation.id

    def test_returns_404_for_nonexistent_conversation(self, client):
        response = client.patch(
            "/api/conversations/99999",
            json={"title": "Nope"},
        )
        assert response.status_code == 404

    def test_returns_422_for_missing_title(self, client, db_session, project_with_conversation):
        _, conversation = project_with_conversation

        response = client.patch(
            f"/api/conversations/{conversation.id}",
            json={},
        )
        assert response.status_code == 422


class TestDeleteConversation:
    """Tests for DELETE /api/conversations/{id}."""

    def test_deletes_conversation(self, client, db_session, project_with_conversation):
        _, conversation = project_with_conversation

        response = client.delete(f"/api/conversations/{conversation.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify conversation is deleted
        conversation_repo = ConversationRepository(db_session)
        assert conversation_repo.get_by_id(conversation.id) is None

    def test_returns_404_for_nonexistent_conversation(self, client):
        response = client.delete("/api/conversations/99999")
        assert response.status_code == 404
