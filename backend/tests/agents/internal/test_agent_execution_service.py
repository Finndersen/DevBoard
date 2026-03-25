"""Tests for PydanticAIAgentExecutionService with Role-based architecture."""

import datetime
from unittest.mock import Mock

import pytest
from pydantic_ai import Tool
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from sqlalchemy.orm import Session

from devboard.agents.engines import AgentEngine
from devboard.agents.engines.internal import PydanticAIAgentExecutionService, PydanticAIConversationHistoryService
from devboard.agents.events import MessageRole, TextMessage, ToolCall, ToolCallRequest
from devboard.agents.roles import AgentRole, AgentRoleType
from devboard.api.schemas.agent_conversation import (
    ToolApprovalDecision,
)
from devboard.db.models import Conversation, ParentEntityType
from devboard.db.repositories.conversation import ConversationRepository


class MockAgentRole(AgentRole):
    """Mock role for testing."""

    def get_system_prompt(self) -> str:
        return "Test system prompt"

    def get_tools(self) -> list[Tool]:
        return []

    async def get_context_content(self) -> str:
        return "Test context"


class TestPydanticAIAgentExecutionService:
    """Test PydanticAIAgentExecutionService functionality."""

    @pytest.fixture
    def mock_role(self):
        """Create mock role."""
        return MockAgentRole()

    @pytest.fixture
    def conversation(self, db_session: Session) -> Conversation:
        """Create a test conversation."""
        conversation_repo = ConversationRepository(db_session)
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
    def history_service(self, conversation_repo, conversation):
        """Create PydanticAIConversationHistoryService instance."""
        return PydanticAIConversationHistoryService(
            conversation=conversation,
            conversation_repository=conversation_repo,
        )

    @pytest.fixture
    def service(
        self,
        mock_role,
        conversation_repo,
        conversation,
        history_service,
        mock_agent_config_service,
    ):
        """Create PydanticAIAgentExecutionService instance."""
        return PydanticAIAgentExecutionService(
            conversation=conversation,
            role=mock_role,
            conversation_repository=conversation_repo,
            history_service=history_service,
            agent_config_service=mock_agent_config_service,
            working_dir="/test/working_dir",
        )

    @pytest.mark.asyncio
    async def test_service_initialization(self, service, mock_role, conversation):
        """Test service initializes with role."""
        assert service.conversation == conversation
        assert service.role == mock_role

    @pytest.mark.asyncio
    async def test_send_message_text_response(self, service, monkeypatch):
        """Test sending a message that returns a text response."""

        # Mock agent stream_events to yield conversation events
        async def mock_stream_events(prompt_or_approvals):
            yield TextMessage(
                role=MessageRole.AGENT,
                text_content="Test response",
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        # Mock get_new_messages to return model messages
        def mock_get_new_messages():
            return [
                ModelRequest(parts=[UserPromptPart(content="Test message")]),
                ModelResponse(parts=[TextPart(content="Test response")]),
            ]

        # Mock agent instance
        mock_agent_instance = Mock()
        mock_agent_instance.stream_events = mock_stream_events
        mock_agent_instance.get_new_messages = mock_get_new_messages

        # Patch _get_agent to return our mock
        monkeypatch.setattr(service, "_get_agent", lambda conversation_history, extra_tools=None: mock_agent_instance)

        events = await service.send_message_or_approval(message_or_approvals="Test message")

        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0].event_type == "message"
        assert events[0].text_content == "Test response"
        assert events[0].role == MessageRole.AGENT

    @pytest.mark.asyncio
    async def test_send_message_tool_request(self, service, monkeypatch):
        """Test sending a message that returns tool requests."""

        # Mock agent stream_events to yield conversation events including tool call request
        async def mock_stream_events(prompt_or_approvals):
            timestamp = datetime.datetime.now(datetime.UTC)
            yield ToolCall(
                tool_call_id="tool_123",
                tool_name="edit_document",
                tool_args={"edits": [{"find": "old", "replace": "new"}]},
                timestamp=timestamp,
            )
            yield ToolCallRequest(
                tool_call_id="tool_123",
                tool_name="edit_document",
                tool_args={"edits": [{"find": "old", "replace": "new"}]},
                timestamp=timestamp,
            )

        # Mock get_new_messages to return model messages
        def mock_get_new_messages():
            return [
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

        # Mock agent instance
        mock_agent_instance = Mock()
        mock_agent_instance.stream_events = mock_stream_events
        mock_agent_instance.get_new_messages = mock_get_new_messages

        # Patch _get_agent to return our mock
        monkeypatch.setattr(service, "_get_agent", lambda conversation_history, extra_tools=None: mock_agent_instance)

        events = await service.send_message_or_approval(message_or_approvals="Edit this")

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

        # Mock agent stream_events to yield a text response after approval
        async def mock_stream_events(prompt_or_approvals):
            yield TextMessage(
                role=MessageRole.AGENT,
                text_content="Document updated successfully",
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        # Mock get_new_messages to return model messages
        def mock_get_new_messages():
            return [
                ModelResponse(parts=[TextPart(content="Document updated successfully")]),
            ]

        # Mock agent instance
        mock_agent_instance = Mock()
        mock_agent_instance.stream_events = mock_stream_events
        mock_agent_instance.get_new_messages = mock_get_new_messages

        # Patch _get_agent to return our mock
        monkeypatch.setattr(service, "_get_agent", lambda conversation_history, extra_tools=None: mock_agent_instance)

        # Process approvals
        approvals = {"tool_123": ToolApprovalDecision(approved=True)}
        events = await service.send_message_or_approval(message_or_approvals=approvals)

        assert isinstance(events, list)
        assert len(events) >= 1
        # Should have at least the final message
        assert any(e.event_type == "message" for e in events)
