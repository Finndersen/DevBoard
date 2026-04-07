"""Tests for PydanticAIAgentExecutionService with Role-based architecture."""

import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai import Tool
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from sqlalchemy.orm import Session

from devboard.agents.engines import AgentEngine
from devboard.agents.engines.internal import PydanticAIAgentExecutionService, PydanticAIConversationHistoryService
from devboard.agents.events import ContextUsage, MessageRole, TextMessage
from devboard.agents.roles import AgentRole, AgentRoleType
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
        expected = TextMessage(
            role=MessageRole.AGENT,
            text_content="Test response",
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        mock_agent_instance = Mock()
        mock_agent_instance.run = AsyncMock(return_value=expected)
        mock_agent_instance.get_new_messages = Mock(
            return_value=[
                ModelRequest(parts=[UserPromptPart(content="Test message")]),
                ModelResponse(parts=[TextPart(content="Test response")]),
            ]
        )

        monkeypatch.setattr(service, "_get_agent", lambda conversation_history, extra_tools=None: mock_agent_instance)

        result = await service.send_message_or_approval(message="Test message")

        assert isinstance(result, TextMessage)
        assert result.text_content == "Test response"
        assert result.role == MessageRole.AGENT

    @pytest.mark.asyncio
    async def test_stream_events_sets_last_usage(self, service, monkeypatch):
        """last_usage is populated from agent.get_context_usage() after stream completes."""
        expected_usage = ContextUsage(
            input_tokens=200,
            output_tokens=80,
            cache_read_tokens=1000,
            cache_write_tokens=300,
        )

        async def mock_stream_events(_msg_or_approvals):
            yield TextMessage(
                role=MessageRole.AGENT,
                text_content="Done.",
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        mock_agent = Mock()
        mock_agent.stream_events = mock_stream_events
        mock_agent.get_new_messages = Mock(return_value=[])
        mock_agent.get_context_usage = Mock(return_value=expected_usage)
        mock_agent.last_run_result = Mock()

        monkeypatch.setattr(service, "_get_agent", lambda conversation_history, extra_tools=None: mock_agent)

        events = []
        async for event in service.stream_events_for_message_or_approval("Hello"):
            events.append(event)

        assert service.last_usage == expected_usage
        mock_agent.get_context_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_events_last_usage_none_when_no_result(self, service, monkeypatch):
        """last_usage remains None when agent has no run result."""

        async def mock_stream_events(_msg_or_approvals):
            yield TextMessage(
                role=MessageRole.AGENT,
                text_content="Done.",
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        mock_agent = Mock()
        mock_agent.stream_events = mock_stream_events
        mock_agent.get_new_messages = Mock(return_value=[])
        mock_agent.get_context_usage = Mock(return_value=None)
        mock_agent.last_run_result = None

        monkeypatch.setattr(service, "_get_agent", lambda conversation_history, extra_tools=None: mock_agent)

        events = []
        async for event in service.stream_events_for_message_or_approval("Hello"):
            events.append(event)

        assert service.last_usage is None
