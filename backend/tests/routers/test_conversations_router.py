"""Tests for conversations router."""

from unittest.mock import Mock, patch

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, UserPromptPart

from devboard.agents.engines import AgentEngine
from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.roles import AgentRoleType
from devboard.db.models import Conversation, ParentEntityType, Project
from devboard.db.models.document import DocumentType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories import ConversationRepository, DocumentRepository, ProjectRepository, TaskRepository


@pytest.fixture
def test_project(db_session) -> Project:
    """Create a test project."""
    document_repo = DocumentRepository(db_session)
    specification_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")

    project_repo = ProjectRepository(db_session)
    project = project_repo.create(
        name="Test Project",
        description="A test project for development",
        specification=specification_doc,
    )
    db_session.commit()
    return project


@pytest.fixture
def test_conversation(db_session, test_project) -> Conversation:
    """Create a test conversation for a project."""
    conversation_repo = ConversationRepository(db_session)
    conversation = conversation_repo.create(
        parent_entity_type=ParentEntityType.PROJECT,
        parent_entity_id=test_project.id,
        agent_role=AgentRoleType.PROJECT,
        engine=AgentEngine.INTERNAL,
        model_id="anthropic:claude-sonnet-4.5",
        is_active=True,
    )
    db_session.commit()
    return conversation


@pytest.fixture
def test_task(db_session, test_project) -> Task:
    """Create a test task."""
    document_repo = DocumentRepository(db_session)
    specification_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "Test task specification")

    task_repo = TaskRepository(db_session)
    task = task_repo.create(
        project_id=test_project.id,
        title="Test Task",
        status=TaskStatus.PLANNING,
        specification=specification_doc,
    )
    db_session.commit()
    return task


@pytest.fixture
def test_task_conversation(db_session, test_task) -> Conversation:
    """Create a test conversation for a task."""
    conversation_repo = ConversationRepository(db_session)
    conversation = conversation_repo.create(
        parent_entity_type=ParentEntityType.TASK,
        parent_entity_id=test_task.id,
        agent_role=AgentRoleType.TASK_PLANNING,
        engine=AgentEngine.INTERNAL,
        model_id="anthropic:claude-sonnet-4.5",
        is_active=True,
    )
    db_session.commit()
    return conversation


class TestConversationsRouter:
    """Test conversations router endpoints."""

    def test_get_conversation_messages_empty(self, client, test_conversation):
        """Test getting messages for a conversation with no messages."""
        response = client.get(f"/api/conversations/{test_conversation.id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []
        assert data["context_usage"] is None

    def test_get_conversation_messages_with_data(self, client, db_session, test_conversation):
        """Test getting messages for a conversation with existing messages."""
        conversation_repo = ConversationRepository(db_session)

        # Create test messages
        user_msg = ModelRequest(parts=[UserPromptPart(content="Hello, can you help me?")])
        agent_msg = ModelResponse(parts=[TextPart(content="Of course! How can I assist you?")])

        conversation_repo.create_message(test_conversation.id, user_msg)
        conversation_repo.create_message(test_conversation.id, agent_msg)
        db_session.commit()

        response = client.get(f"/api/conversations/{test_conversation.id}/messages")
        assert response.status_code == 200

        data = response.json()
        messages = data["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["text_content"] == "Hello, can you help me?"
        assert messages[1]["role"] == "agent"
        assert messages[1]["text_content"] == "Of course! How can I assist you?"

    def test_get_conversation_messages_includes_tool_calls(self, client, db_session, test_conversation):
        """Test that tool call events are included in results."""
        conversation_repo = ConversationRepository(db_session)

        # Create messages including a tool call
        user_msg = ModelRequest(parts=[UserPromptPart(content="Edit this document")])
        tool_call_msg = ModelResponse(
            parts=[ToolCallPart(tool_name="edit_document", tool_call_id="tool_123", args={"content": "new"})]
        )
        agent_response = ModelResponse(parts=[TextPart(content="I've made the requested edits")])

        conversation_repo.create_message(test_conversation.id, user_msg)
        conversation_repo.create_message(test_conversation.id, tool_call_msg)
        conversation_repo.create_message(test_conversation.id, agent_response)
        db_session.commit()

        response = client.get(f"/api/conversations/{test_conversation.id}/messages")
        assert response.status_code == 200

        data = response.json()
        events = data["messages"]
        # Should have user message, tool call, and final agent response
        assert len(events) == 3
        assert events[0]["event_type"] == "message"
        assert events[0]["text_content"] == "Edit this document"
        assert events[1]["event_type"] == "tool_call"
        assert events[1]["tool_name"] == "edit_document"
        assert events[1]["tool_call_id"] == "tool_123"
        assert events[2]["event_type"] == "message"
        assert events[2]["text_content"] == "I've made the requested edits"

    def test_send_conversation_message(self, client, test_conversation):
        """Test sending a message starts a background execution and returns conversation_id."""
        message_request = {"message": "Help me analyze my project and answer questions."}

        with patch("devboard.api.routers.conversations.get_execution_manager") as mock_get_mgr:
            mock_manager = Mock()
            mock_get_mgr.return_value = mock_manager
            response = client.post(f"/api/conversations/{test_conversation.id}/messages", json=message_request)

        assert response.status_code == 200
        assert response.json() == {"conversation_id": test_conversation.id}
        mock_manager.start_agent_execution.assert_called_once()

    def test_send_conversation_message_returns_tool_request(self, client, test_conversation):
        """Test that 409 is returned when an execution is already active."""
        message_request = {"message": "Please update the document with better content"}

        with patch("devboard.api.routers.conversations.get_execution_manager") as mock_get_mgr:
            mock_manager = Mock()
            mock_get_mgr.return_value = mock_manager
            mock_manager.start_agent_execution.side_effect = ConversationBusyError(test_conversation.id)
            response = client.post(f"/api/conversations/{test_conversation.id}/messages", json=message_request)

        assert response.status_code == 409
        assert "already active" in response.json()["detail"]

    def test_reset_conversation_success(self, client, db_session, test_conversation, test_project):
        """Test resetting a conversation creates a new one and clears messages."""
        conversation_repo = ConversationRepository(db_session)

        # Create test messages
        user_msg = ModelRequest(parts=[UserPromptPart(content="Message 1")])
        agent_msg = ModelResponse(parts=[TextPart(content="Response 1")])

        conversation_repo.create_message(test_conversation.id, user_msg)
        conversation_repo.create_message(test_conversation.id, agent_msg)
        db_session.commit()

        # Verify messages exist
        messages = conversation_repo.get_messages(test_conversation.id)
        assert len(messages) == 2

        # Reset conversation
        response = client.post(f"/api/conversations/{test_conversation.id}/reset")
        assert response.status_code == 200

        reset_response = response.json()
        assert "new_conversation_id" in reset_response
        assert reset_response["message"] == "Conversation reset successfully."
        new_conversation_id = reset_response["new_conversation_id"]

        # Verify new conversation exists with correct config
        new_conversation = conversation_repo.get_by_id(new_conversation_id)
        assert new_conversation is not None
        assert new_conversation.parent_entity_type == ParentEntityType.PROJECT
        assert new_conversation.parent_entity_id == test_project.id
        assert new_conversation.is_active is True

        # Verify new conversation has no messages (key validation: messages were cleared)
        messages = conversation_repo.get_messages(new_conversation_id)
        assert len(messages) == 0

    def test_reset_conversation_empty(self, client, db_session, test_conversation):
        """Test resetting a conversation with no messages."""
        response = client.post(f"/api/conversations/{test_conversation.id}/reset")
        assert response.status_code == 200

        reset_response = response.json()
        assert "new_conversation_id" in reset_response
        assert reset_response["message"] == "Conversation reset successfully."
        new_conversation_id = reset_response["new_conversation_id"]

        # Verify new conversation exists
        conversation_repo = ConversationRepository(db_session)
        new_conversation = conversation_repo.get_by_id(new_conversation_id)
        assert new_conversation is not None
        assert new_conversation.is_active is True

    def test_reset_conversation_updates_parent_entity(self, client, db_session, test_project):
        """Test that resetting a conversation updates the parent entity's conversation reference."""
        conversation_repo = ConversationRepository(db_session)

        # Create a project conversation and link it to the project
        conversation = conversation_repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=test_project.id,
            agent_role=AgentRoleType.PROJECT,
            engine=AgentEngine.INTERNAL,
            model_id="anthropic:claude-sonnet-4.5",
            is_active=True,
        )
        test_project.default_conversation_id = conversation.id
        db_session.commit()

        # Reset conversation
        response = client.post(f"/api/conversations/{conversation.id}/reset")
        assert response.status_code == 200

        reset_response = response.json()
        new_conversation_id = reset_response["new_conversation_id"]

        # Verify parent entity now references new conversation
        db_session.refresh(test_project)
        assert test_project.default_conversation_id == new_conversation_id

        # Verify new conversation is valid
        new_conversation = conversation_repo.get_by_id(new_conversation_id)
        assert new_conversation is not None
        assert new_conversation.parent_entity_id == test_project.id

    def test_stream_conversation_message(self, client, test_conversation):
        """Test that POST /messages starts background execution and returns conversation_id."""
        message_request = {"message": "Help me analyze my project and answer questions."}

        with patch("devboard.api.routers.conversations.get_execution_manager") as mock_get_mgr:
            mock_manager = Mock()
            mock_get_mgr.return_value = mock_manager
            response = client.post(f"/api/conversations/{test_conversation.id}/messages", json=message_request)

        assert response.status_code == 200
        assert response.json() == {"conversation_id": test_conversation.id}
        mock_manager.start_agent_execution.assert_called_once()

    def test_stream_conversation_message_returns_multiple_events(self, client, test_conversation):
        """Test that duplicate POST /messages with active execution returns 409."""
        message_request = {"message": "First message"}

        with patch("devboard.api.routers.conversations.get_execution_manager") as mock_get_mgr:
            mock_manager = Mock()
            mock_get_mgr.return_value = mock_manager
            mock_manager.start_agent_execution.side_effect = ConversationBusyError(test_conversation.id)
            response = client.post(f"/api/conversations/{test_conversation.id}/messages", json=message_request)

        assert response.status_code == 409

    def test_stream_conversation_message_with_tool_request(self, client, test_conversation):
        """Test that POST /messages for completed task returns 400."""
        message_request = {"message": "Please update the document"}

        # Patch Task.status to be COMPLETE to test the validation
        with patch("devboard.api.routers.conversations.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            # Test with a project conversation (no completed task check)
            response = client.post(f"/api/conversations/{test_conversation.id}/messages", json=message_request)

        assert response.status_code == 200

    def test_stream_approve_conversation_tools(self, client, test_conversation):
        """Test that POST /approve-tools starts background execution and returns conversation_id."""
        approval_request = {"approvals": {"test_call_1": {"approved": True, "feedback": "Looks good"}}}

        with patch("devboard.api.routers.conversations.get_execution_manager") as mock_get_mgr:
            mock_manager = Mock()
            mock_get_mgr.return_value = mock_manager
            response = client.post(f"/api/conversations/{test_conversation.id}/approve-tools", json=approval_request)

        assert response.status_code == 200
        assert response.json() == {"conversation_id": test_conversation.id}
        mock_manager.start_agent_execution.assert_called_once()

    def test_stream_approve_conversation_tools_multiple_events(self, client, test_conversation):
        """Test that POST /approve-tools with active execution returns 409."""
        approval_request = {"approvals": {"call_1": {"approved": True}}}

        with patch("devboard.api.routers.conversations.get_execution_manager") as mock_get_mgr:
            mock_manager = Mock()
            mock_get_mgr.return_value = mock_manager
            mock_manager.start_agent_execution.side_effect = ConversationBusyError(test_conversation.id)
            response = client.post(f"/api/conversations/{test_conversation.id}/approve-tools", json=approval_request)

        assert response.status_code == 409

    def test_interrupt_conversation(self, client, test_conversation):
        """Test that POST /interrupt signals the active execution to stop."""
        with patch("devboard.api.routers.conversations.get_execution_manager") as mock_get_mgr:
            mock_manager = Mock()
            mock_get_mgr.return_value = mock_manager
            mock_manager.request_interrupt.return_value = True
            response = client.post(f"/api/conversations/{test_conversation.id}/interrupt")

        assert response.status_code == 200
        assert response.json() == {"status": "interrupt_requested"}
        mock_manager.request_interrupt.assert_called_once_with(test_conversation.id)

    def test_interrupt_conversation_no_active_execution(self, client, test_conversation):
        """Test that POST /interrupt returns 404 when no active execution."""
        with patch("devboard.api.routers.conversations.get_execution_manager") as mock_get_mgr:
            mock_manager = Mock()
            mock_get_mgr.return_value = mock_manager
            mock_manager.request_interrupt.return_value = False
            response = client.post(f"/api/conversations/{test_conversation.id}/interrupt")

        assert response.status_code == 404
