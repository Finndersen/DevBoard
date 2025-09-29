"""Tests for conversations router."""

from unittest.mock import Mock

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.run import AgentRunResult
from pydantic_ai.tools import DeferredToolRequests

from devboard.api.dependencies.agents import get_conversation_agent
from devboard.api.main import app
from devboard.db.models import Conversation, ParentEntityType, Project
from devboard.db.repositories import ConversationRepository, ProjectRepository


@pytest.fixture
def client_with_mock_agent(client, mock_agent):
    """Client with mocked conversation agent."""
    app.dependency_overrides[get_conversation_agent] = lambda: mock_agent
    yield client
    if get_conversation_agent in app.dependency_overrides:
        del app.dependency_overrides[get_conversation_agent]


@pytest.fixture
def test_project(db_session) -> Project:
    """Create a test project."""
    project_repo = ProjectRepository(db_session)
    project = project_repo.create(name="Test Project", description="A test project for development")
    db_session.commit()
    return project


@pytest.fixture
def test_conversation(db_session, test_project) -> Conversation:
    """Create a test conversation for a project."""
    conversation_repo = ConversationRepository(db_session)
    conversation = conversation_repo.get_or_create_for_entity(ParentEntityType.PROJECT, test_project.id)
    db_session.commit()
    return conversation


class TestConversationsRouter:
    """Test conversations router endpoints."""

    def test_get_conversation_messages_empty(self, client, test_conversation):
        """Test getting messages for a conversation with no messages."""
        response = client.get(f"/api/conversations/{test_conversation.id}/messages")
        assert response.status_code == 200
        assert response.json() == []

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

        messages = response.json()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["text_content"] == "Hello, can you help me?"
        assert messages[1]["role"] == "agent"
        assert messages[1]["text_content"] == "Of course! How can I assist you?"

    def test_get_conversation_messages_excludes_tool_calls(self, client, db_session, test_conversation):
        """Test that tool call messages are excluded from results."""
        conversation_repo = ConversationRepository(db_session)

        # Create messages including a tool call
        user_msg = ModelRequest(parts=[UserPromptPart(content="Edit this document")])
        tool_call_msg = ModelResponse(parts=[ToolCallPart(tool_name="edit_document", tool_call_id="tool_123", args={})])
        agent_response = ModelResponse(parts=[TextPart(content="I've made the requested edits")])

        conversation_repo.create_message(test_conversation.id, user_msg)
        conversation_repo.create_message(test_conversation.id, tool_call_msg)
        conversation_repo.create_message(test_conversation.id, agent_response)
        db_session.commit()

        response = client.get(f"/api/conversations/{test_conversation.id}/messages")
        assert response.status_code == 200

        messages = response.json()
        # Should only have user message and final agent response, not tool call
        assert len(messages) == 2
        assert messages[0]["text_content"] == "Edit this document"
        assert messages[1]["text_content"] == "I've made the requested edits"

    def test_send_conversation_message(self, client_with_mock_agent, test_conversation, mock_agent):
        """Test sending a message to a conversation."""
        message_request = {"message": "Help me analyze my project and answer questions."}

        response = client_with_mock_agent.post(
            f"/api/conversations/{test_conversation.id}/messages", json=message_request
        )
        assert response.status_code == 200

        conversation_response = response.json()
        assert conversation_response["type"] == "message"
        assert conversation_response["message"]["role"] == "agent"
        assert "I can help you analyze" in conversation_response["message"]["text_content"]

        # Verify the mock agent was called correctly
        mock_agent.run.assert_called_once()
        args, kwargs = mock_agent.run.call_args
        assert kwargs["prompt_or_approvals"] == "Help me analyze my project and answer questions."

    def test_send_conversation_message_returns_tool_request(
        self, client_with_mock_agent, test_conversation, mock_agent
    ):
        """Test sending a message that triggers a tool request."""
        # Mock the agent to return a tool request
        tool_call_part = ToolCallPart(
            tool_name="edit_document",
            tool_call_id="test_call_1",
            args={"edits": [{"find": "old", "replace": "new"}]},
        )

        mock_result = Mock(spec=AgentRunResult)
        mock_result.output = DeferredToolRequests(approvals=[tool_call_part])
        mock_result.new_messages = Mock(
            return_value=[
                ModelRequest(parts=[UserPromptPart(content="Edit the document")]),
                ModelResponse(parts=[tool_call_part]),
            ]
        )
        # Override the side_effect to return our tool request result
        mock_agent.run.side_effect = None
        mock_agent.run.return_value = mock_result

        message_request = {"message": "Please update the document with better content"}

        response = client_with_mock_agent.post(
            f"/api/conversations/{test_conversation.id}/messages", json=message_request
        )
        assert response.status_code == 200

        conversation_response = response.json()
        assert conversation_response["type"] == "tool_request"
        assert conversation_response["tool_requests"] is not None
        assert len(conversation_response["tool_requests"]) == 1
        assert conversation_response["tool_requests"][0]["tool_name"] == "edit_document"
        assert conversation_response["tool_requests"][0]["tool_call_id"] == "test_call_1"
        assert conversation_response["message"] is None

    def test_approve_conversation_tools(self, client_with_mock_agent, test_conversation, db_session, mock_agent):
        """Test approving tool calls in a conversation."""
        conversation_repo = ConversationRepository(db_session)

        # Setup: Add existing messages including a tool call message
        user_msg = ModelRequest(parts=[UserPromptPart(content="Edit this document")])
        tool_call_msg = ModelResponse(
            parts=[ToolCallPart(tool_name="edit_document", tool_call_id="test_call_1", args={})]
        )

        conversation_repo.create_message(test_conversation.id, user_msg)
        conversation_repo.create_message(test_conversation.id, tool_call_msg)
        db_session.commit()

        # Mock the agent to return approval result
        mock_result = Mock(spec=AgentRunResult)
        mock_result.output = "Great! I've processed your tool approvals and made the requested edits."
        mock_result.new_messages = Mock(
            return_value=[
                ModelResponse(
                    parts=[TextPart(content="Great! I've processed your tool approvals and made the requested edits.")]
                )
            ]
        )
        mock_agent.run.return_value = mock_result

        approval_request = {"approvals": {"test_call_1": {"approved": True, "feedback": "Looks good"}}}

        response = client_with_mock_agent.post(
            f"/api/conversations/{test_conversation.id}/approve-tools", json=approval_request
        )
        assert response.status_code == 200

        conversation_response = response.json()
        assert conversation_response["type"] == "message"
        assert conversation_response["message"]["role"] == "agent"
        assert "tool approvals" in conversation_response["message"]["text_content"]

        # Verify the mock agent was called with tool approvals
        mock_agent.run.assert_called_once()
        args, kwargs = mock_agent.run.call_args
        assert not isinstance(kwargs["prompt_or_approvals"], str)

    def test_approve_conversation_tools_mixed_approvals(
        self, client_with_mock_agent, test_conversation, db_session, mock_agent
    ):
        """Test approving some tools and denying others."""
        conversation_repo = ConversationRepository(db_session)

        # Setup: Add existing messages with multiple tool calls
        user_msg = ModelRequest(parts=[UserPromptPart(content="Make several edits")])
        tool_call_msg = ModelResponse(
            parts=[
                ToolCallPart(tool_name="edit_document", tool_call_id="call_1", args={}),
                ToolCallPart(tool_name="delete_file", tool_call_id="call_2", args={}),
            ]
        )

        conversation_repo.create_message(test_conversation.id, user_msg)
        conversation_repo.create_message(test_conversation.id, tool_call_msg)
        db_session.commit()

        # Mock the agent to return approval result
        mock_result = Mock(spec=AgentRunResult)
        mock_result.output = "I've processed your approvals. I made the edit but skipped the deletion."
        mock_result.new_messages = Mock(
            return_value=[
                ModelResponse(
                    parts=[TextPart(content="I've processed your approvals. I made the edit but skipped the deletion.")]
                )
            ]
        )
        mock_agent.run.return_value = mock_result

        approval_request = {
            "approvals": {
                "call_1": {"approved": True},
                "call_2": {"approved": False, "feedback": "Don't delete this file"},
            }
        }

        response = client_with_mock_agent.post(
            f"/api/conversations/{test_conversation.id}/approve-tools", json=approval_request
        )
        assert response.status_code == 200

        conversation_response = response.json()
        assert conversation_response["type"] == "message"
        assert conversation_response["message"] is not None

    def test_clear_conversation_messages_success(self, client, db_session, test_conversation):
        """Test clearing all messages from a conversation."""
        conversation_repo = ConversationRepository(db_session)

        # Create test messages
        user_msg = ModelRequest(parts=[UserPromptPart(content="Message 1")])
        agent_msg = ModelResponse(parts=[TextPart(content="Response 1")])
        user_msg2 = ModelRequest(parts=[UserPromptPart(content="Message 2")])

        conversation_repo.create_message(test_conversation.id, user_msg)
        conversation_repo.create_message(test_conversation.id, agent_msg)
        conversation_repo.create_message(test_conversation.id, user_msg2)
        db_session.commit()

        # Verify messages exist
        messages = conversation_repo.get_messages(test_conversation.id)
        assert len(messages) == 3

        # Clear messages
        response = client.delete(f"/api/conversations/{test_conversation.id}/messages")
        assert response.status_code == 200

        delete_response = response.json()
        assert delete_response["success"] is True
        assert "3" in delete_response["message"]
        assert "Cleared" in delete_response["message"]

        # Verify messages are deleted
        messages = conversation_repo.get_messages(test_conversation.id)
        assert len(messages) == 0

    def test_clear_conversation_messages_empty(self, client, test_conversation):
        """Test clearing messages from a conversation with no messages."""
        response = client.delete(f"/api/conversations/{test_conversation.id}/messages")
        assert response.status_code == 200

        delete_response = response.json()
        assert delete_response["success"] is True
        assert "0" in delete_response["message"]
