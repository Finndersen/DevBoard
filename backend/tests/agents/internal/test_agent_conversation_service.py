"""Tests for PydanticAIConversationService with Role-based architecture."""

from unittest.mock import MagicMock, Mock

import pytest
from pydantic_ai import AgentRunResultEvent, FunctionToolCallEvent, Tool
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult
from pydantic_ai.tools import (
    DeferredToolRequests,
    ToolFuncEither,
)
from sqlalchemy.orm import Session

from devboard.agents.engines.internal import PydanticAIConversationService
from devboard.agents.roles.base import Role
from devboard.agents.roles.types import AgentRoleType
from devboard.api.schemas.agent_conversation import (
    MessageRole,
    ToolApprovalDecision,
)
from devboard.db.models import Conversation
from devboard.db.repositories.conversation import ConversationRepository


class MockRole(Role):
    """Mock role for testing."""

    def get_system_prompt(self) -> str:
        return "Test system prompt"

    def get_tools(self) -> list[Tool | ToolFuncEither]:
        return []

    async def get_context_content(self) -> str:
        return "Test context"


class TestPydanticAIConversationService:
    """Test PydanticAIConversationService functionality."""

    @pytest.fixture
    def mock_role(self):
        """Create mock role."""
        return MockRole()

    @pytest.fixture
    def conversation(self, db_session: Session) -> Conversation:
        """Create a test conversation."""
        conversation_repo = ConversationRepository(db_session)
        from devboard.agents.engines.agent_engines import AgentEngine
        from devboard.db.models import ParentEntityType

        conversation = conversation_repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=1,
            agent_role=AgentRoleType.PROJECT,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
            is_active=True,
        )
        db_session.commit()
        return conversation

    @pytest.fixture
    def conversation_repo(self, db_session: Session) -> ConversationRepository:
        """Create conversation repository."""
        return ConversationRepository(db_session)

    @pytest.fixture
    def service(self, mock_role, conversation_repo, conversation):
        """Create PydanticAIConversationService instance."""
        return PydanticAIConversationService(
            conversation=conversation,
            role=mock_role,
            conversation_repository=conversation_repo,
        )

    @pytest.mark.asyncio
    async def test_service_initialization(self, service, mock_role, conversation):
        """Test service initializes with role."""
        assert service.conversation == conversation
        assert service.role == mock_role

    @pytest.mark.asyncio
    async def test_send_message_text_response(self, service, monkeypatch):
        """Test sending a message that returns a text response."""
        # Mock agent run to return a text response
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = "Test response"
        mock_result.new_messages.return_value = [
            ModelRequest(parts=[UserPromptPart(content="Test message")]),
            ModelResponse(parts=[TextPart(content="Test response")]),
        ]

        # Create async generator for mock stream_events
        async def mock_stream_events(**kwargs):
            yield AgentRunResultEvent(result=mock_result)

        # Mock agent instance
        mock_agent_instance = Mock()
        mock_agent_instance.stream_events = mock_stream_events

        # Patch _get_agent to return our mock
        monkeypatch.setattr(service, "_get_agent", lambda: mock_agent_instance)

        events = await service.send_message(message="Test message")

        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0].event_type == "message"
        assert events[0].text_content == "Test response"
        assert events[0].role == MessageRole.AGENT

    @pytest.mark.asyncio
    async def test_send_message_tool_request(self, service, monkeypatch):
        """Test sending a message that returns tool requests."""
        # Create mock deferred tool requests
        mock_tool_request = MagicMock()
        mock_tool_request.tool_call_id = "tool_123"
        mock_tool_request.tool_name = "edit_document"
        mock_tool_request.args = {"edits": [{"find": "old", "replace": "new"}]}

        mock_deferred = DeferredToolRequests(approvals=[mock_tool_request])

        # Mock agent run to return deferred tool requests
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_deferred
        mock_result.new_messages.return_value = [
            ModelRequest(parts=[UserPromptPart(content="Edit this")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="edit_document",
                        tool_call_id="tool_123",
                        args={"edits": [{"find": "old", "replace": "new"}]},
                    )
                ]
            ),
        ]

        # Create async generator for mock
        async def mock_stream_events(**kwargs):
            tool_call_part = ToolCallPart(
                tool_name="edit_document",
                tool_call_id="tool_123",
                args={"edits": [{"find": "old", "replace": "new"}]},
            )
            yield FunctionToolCallEvent(part=tool_call_part)
            yield AgentRunResultEvent(result=mock_result)

        # Mock agent instance
        mock_agent_instance = Mock()
        mock_agent_instance.stream_events = mock_stream_events

        # Patch _get_agent to return our mock
        monkeypatch.setattr(service, "_get_agent", lambda: mock_agent_instance)

        events = await service.send_message(message="Edit this")

        assert isinstance(events, list)
        assert len(events) == 2
        # First event should be the tool call
        assert events[0].event_type == "tool_call"
        assert events[0].tool_call_id == "tool_123"
        assert events[0].tool_name == "edit_document"
        # Second event should be the tool call request
        assert events[1].event_type == "tool_call_request"
        assert events[1].tool_call_id == "tool_123"
        assert events[1].tool_name == "edit_document"

    @pytest.mark.asyncio
    async def test_process_tool_approvals(self, service, conversation_repo, conversation, db_session, monkeypatch):
        """Test processing tool approval decisions."""
        # Setup: Add existing messages including a tool call message
        user_pydantic_msg = ModelRequest(parts=[UserPromptPart(content="Edit this document")])
        tool_call_pydantic_msg = ModelResponse(
            parts=[ToolCallPart(tool_name="edit_document", tool_call_id="tool_123", args={})]
        )

        conversation_repo.create_message(conversation.id, user_pydantic_msg)
        conversation_repo.create_message(conversation.id, tool_call_pydantic_msg)
        db_session.commit()

        # Mock agent run to return a text response after approval
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = "Document updated successfully"
        mock_result.new_messages.return_value = [
            ModelResponse(parts=[TextPart(content="Document updated successfully")]),
        ]

        # Create async generator for mock
        async def mock_stream_events(**kwargs):
            yield AgentRunResultEvent(result=mock_result)

        # Mock agent instance
        mock_agent_instance = Mock()
        mock_agent_instance.stream_events = mock_stream_events

        # Patch _get_agent to return our mock
        monkeypatch.setattr(service, "_get_agent", lambda: mock_agent_instance)

        # Process approvals
        approvals = {"tool_123": ToolApprovalDecision(approved=True)}
        events = await service.process_tool_approvals(approvals=approvals)

        assert isinstance(events, list)
        assert len(events) >= 1
        # Should have at least the final message
        assert any(e.event_type == "message" for e in events)
