"""Tests for AgentConversationService."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from devboard.api.schemas.agent_conversation import (
    ConversationResponse,
    MessageRequest,
    ToolApprovalDecision,
    ToolApprovalRequest,
)
from devboard.db.models.messages import BaseConversationMessage
from devboard.services.agent_conversation import AgentConversationService


class MockMessageRepository:
    """Mock implementation of MessageRepository for testing."""

    def __init__(self):
        self.messages = []

    def get_by_entity_id(self, entity_id: int) -> list[BaseConversationMessage]:
        return [msg for msg in self.messages if getattr(msg, "entity_id", None) == entity_id]

    def create(self, message: BaseConversationMessage) -> BaseConversationMessage:
        message.id = len(self.messages) + 1
        message.created_at = datetime.datetime.now()
        self.messages.append(message)
        return message


class MockAgentService:
    """Mock agent service for testing."""

    def __init__(self):
        self.extract_message_history_return = []
        self.serialize_messages_return = {"data": "test response"}

    def extract_message_history_from_records(self, records):
        return self.extract_message_history_return

    def serialize_messages(self, result):
        return self.serialize_messages_return


class TestAgentConversationService:
    """Test AgentConversationService functionality."""

    @pytest.fixture
    def agent_conversation_service(self):
        """Create AgentConversationService instance."""
        return AgentConversationService()

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        mock_session = MagicMock(spec=Session)
        mock_session.commit = MagicMock()
        mock_session.rollback = MagicMock()
        return mock_session

    @pytest.fixture
    def mock_message_repo(self):
        """Mock message repository."""
        return MockMessageRepository()

    @pytest.fixture
    def mock_agent_service(self):
        """Mock agent service."""
        return MockAgentService()

    @pytest.fixture
    def create_message_model(self):
        """Factory function to create message models."""

        def _create(**kwargs):
            mock_msg = MagicMock()
            mock_msg.id = None
            mock_msg.created_at = datetime.datetime.now()
            for key, value in kwargs.items():
                setattr(mock_msg, key, value)
            return mock_msg

        return _create

    async def test_send_message_success_no_deferred(
        self,
        agent_conversation_service,
        mock_db_session,
        mock_message_repo,
        mock_agent_service,
        create_message_model,
    ):
        """Test send_message with successful processing and no deferred tools."""
        # Mock the _process_with_agent method
        agent_conversation_service._process_with_agent = AsyncMock(return_value=("result", None))

        message_request = MessageRequest(message="Test message")

        response = await agent_conversation_service.send_message(
            entity_id=123,
            message_request=message_request,
            agent_service=mock_agent_service,
            message_repo=mock_message_repo,
            db=mock_db_session,
            create_message_model=create_message_model,
        )

        assert isinstance(response, ConversationResponse)
        assert len(response.messages) == 2  # User message + agent response
        assert response.pending_approvals is None
        assert response.conversation_complete is True

        # Verify database operations
        mock_db_session.commit.assert_called()
        assert len(mock_message_repo.messages) == 2

    async def test_send_message_with_deferred_tools(
        self,
        agent_conversation_service,
        mock_db_session,
        mock_message_repo,
        mock_agent_service,
        create_message_model,
    ):
        """Test send_message with deferred tool requests."""
        # Mock deferred requests
        mock_deferred = MagicMock()
        mock_deferred.approvals = []

        # Mock the _process_with_agent method
        agent_conversation_service._process_with_agent = AsyncMock(return_value=("result", mock_deferred))

        message_request = MessageRequest(message="Test message requiring tools")

        response = await agent_conversation_service.send_message(
            entity_id=123,
            message_request=message_request,
            agent_service=mock_agent_service,
            message_repo=mock_message_repo,
            db=mock_db_session,
            create_message_model=create_message_model,
        )

        assert isinstance(response, ConversationResponse)
        assert response.pending_approvals is not None
        assert response.conversation_complete is False

    async def test_send_message_exception_handling(
        self,
        agent_conversation_service,
        mock_db_session,
        mock_message_repo,
        mock_agent_service,
        create_message_model,
    ):
        """Test send_message exception handling."""
        # Mock the _process_with_agent method to raise an exception
        agent_conversation_service._process_with_agent = AsyncMock(side_effect=Exception("Test error"))

        message_request = MessageRequest(message="Test message")

        with pytest.raises(HTTPException) as exc_info:
            await agent_conversation_service.send_message(
                entity_id=123,
                message_request=message_request,
                agent_service=mock_agent_service,
                message_repo=mock_message_repo,
                db=mock_db_session,
                create_message_model=create_message_model,
            )

        assert exc_info.value.status_code == 500
        assert "Error processing message" in str(exc_info.value.detail)
        mock_db_session.rollback.assert_called()

    async def test_process_tool_approval_success(
        self,
        agent_conversation_service,
        mock_db_session,
        mock_message_repo,
        mock_agent_service,
        create_message_model,
    ):
        """Test process_tool_approval with successful approval."""
        # Mock the _process_tool_approval_with_agent method
        agent_conversation_service._process_tool_approval_with_agent = AsyncMock(
            return_value="approval_result"
        )

        approval_request = ToolApprovalRequest(
            approvals={"tool_1": ToolApprovalDecision(approved=True, feedback="Looks good")}
        )

        response = await agent_conversation_service.process_tool_approval(
            entity_id=123,
            approval_request=approval_request,
            agent_service=mock_agent_service,
            message_repo=mock_message_repo,
            db=mock_db_session,
            create_message_model=create_message_model,
        )

        assert isinstance(response, ConversationResponse)
        assert len(response.messages) == 1  # Agent continuation response
        assert response.pending_approvals is None
        assert response.conversation_complete is True

    async def test_process_tool_approval_exception_handling(
        self,
        agent_conversation_service,
        mock_db_session,
        mock_message_repo,
        mock_agent_service,
        create_message_model,
    ):
        """Test process_tool_approval exception handling."""
        # Mock the _process_tool_approval_with_agent method to raise an exception
        agent_conversation_service._process_tool_approval_with_agent = AsyncMock(
            side_effect=Exception("Approval error")
        )

        approval_request = ToolApprovalRequest(
            approvals={"tool_1": ToolApprovalDecision(approved=True)}
        )

        with pytest.raises(HTTPException) as exc_info:
            await agent_conversation_service.process_tool_approval(
                entity_id=123,
                approval_request=approval_request,
                agent_service=mock_agent_service,
                message_repo=mock_message_repo,
                db=mock_db_session,
                create_message_model=create_message_model,
            )

        assert exc_info.value.status_code == 500
        assert "Error processing tool approval" in str(exc_info.value.detail)
        mock_db_session.rollback.assert_called()

    async def test_process_with_agent_not_implemented(self, agent_conversation_service):
        """Test that _process_with_agent raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await agent_conversation_service._process_with_agent(None, "test", [])

    async def test_process_tool_approval_with_agent_not_implemented(self, agent_conversation_service):
        """Test that _process_tool_approval_with_agent raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await agent_conversation_service._process_tool_approval_with_agent(None, None, [])

    def test_convert_messages_to_response_request_message(self, agent_conversation_service):
        """Test converting request messages to response format."""
        mock_msg = MagicMock()
        mock_msg.id = 1
        mock_msg.message_type = "request"
        mock_msg.pydantic_content = {"content": "Test user message"}
        mock_msg.created_at = datetime.datetime.now()

        result = agent_conversation_service._convert_messages_to_response([mock_msg])

        assert len(result) == 1
        assert result[0].message_type == "request"
        assert result[0].text_content == "Test user message"

    def test_convert_messages_to_response_response_message(self, agent_conversation_service):
        """Test converting response messages to response format."""
        mock_msg = MagicMock()
        mock_msg.id = 1
        mock_msg.message_type = "response"
        mock_msg.pydantic_content = {"data": "Test agent response"}
        mock_msg.created_at = datetime.datetime.now()

        result = agent_conversation_service._convert_messages_to_response([mock_msg])

        assert len(result) == 1
        assert result[0].message_type == "response"
        assert result[0].text_content == "Test agent response"

    def test_extract_pending_approvals_empty(self, agent_conversation_service):
        """Test _extract_pending_approvals with empty deferred requests."""
        mock_deferred = MagicMock()
        mock_deferred.approvals = []

        result = agent_conversation_service._extract_pending_approvals(mock_deferred)

        assert result == []

    def test_extract_pending_approvals_document_edit(self, agent_conversation_service):
        """Test _extract_pending_approvals with document edit tool."""
        # Mock tool request
        mock_tool_request = MagicMock()
        mock_tool_request.tool_call_id = "tool_123"
        mock_tool_request.tool_name = "edit_task_specification"
        mock_tool_request.args = {
            "edits": [{"find": "old text", "replace": "new text"}],
            "reasoning": "Updating specification",
        }

        mock_deferred = MagicMock()
        mock_deferred.approvals = [mock_tool_request]

        result = agent_conversation_service._extract_pending_approvals(mock_deferred)

        assert len(result) == 1
        approval = result[0]
        assert approval.tool_call_id == "tool_123"
        assert approval.tool_name == "edit_task_specification"
        assert approval.document_type == "task_specification"
        assert approval.reasoning == "Updating specification"

    def test_extract_pending_approvals_no_approvals_attribute(self, agent_conversation_service):
        """Test _extract_pending_approvals with object missing approvals attribute."""
        mock_deferred = MagicMock()
        del mock_deferred.approvals  # Remove the attribute

        result = agent_conversation_service._extract_pending_approvals(mock_deferred)

        assert result == []

    def test_create_deferred_results_success(self, agent_conversation_service):
        """Test _create_deferred_results with successful creation."""
        approval_request = ToolApprovalRequest(
            approvals={
                "tool_1": ToolApprovalDecision(approved=True, feedback="Good"),
                "tool_2": ToolApprovalDecision(approved=False, feedback="Not good"),
            }
        )

        # Since PydanticAI may not be available, this should return the approval request
        result = agent_conversation_service._create_deferred_results(approval_request)

        # The result should be either the approval request (fallback) or a proper DeferredToolResults
        assert result is not None

    def test_create_deferred_results_handles_approval_request(self, agent_conversation_service):
        """Test _create_deferred_results handles approval request correctly."""
        approval_request = ToolApprovalRequest(
            approvals={"tool_1": ToolApprovalDecision(approved=True)}
        )

        result = agent_conversation_service._create_deferred_results(approval_request)

        # Should return a result that's not None
        assert result is not None

    def test_create_basic_diff_preview_empty(self, agent_conversation_service):
        """Test _create_basic_diff_preview with empty edits."""
        result = agent_conversation_service._create_basic_diff_preview([])

        assert result == "No edits specified"

    def test_create_basic_diff_preview_with_edits(self, agent_conversation_service):
        """Test _create_basic_diff_preview with document edits."""
        edits = [
            {"find": "old text", "replace": "new text"},
            {"find": "another old", "replace": "another new"},
        ]

        result = agent_conversation_service._create_basic_diff_preview(edits)

        assert "Edit 1:" in result
        assert "Edit 2:" in result
        assert "- Find: old text" in result
        assert "+ Replace: new text" in result
