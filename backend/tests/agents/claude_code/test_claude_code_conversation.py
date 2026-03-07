"""Tests for ClaudeCodeConversationHistoryService session expiration handling."""

import datetime
from unittest.mock import Mock, patch

import pytest
from pydantic_ai import Tool
from sqlalchemy.orm import Session

from devboard.agents.engines import AgentEngine
from devboard.agents.engines.claude_code import (
    ClaudeCodeAgentExecutionService,
    ClaudeCodeConversationHistoryService,
)
from devboard.agents.engines.claude_code.session import (
    AssistantSessionMessage,
    MetaSessionMessage,
    UserSessionMessage,
)
from devboard.agents.engines.claude_code.session.event_converter import session_messages_to_events
from devboard.agents.events import MessageRole, MetaMessage, MetaMessageType, SystemEventType, TextMessage, ToolCall
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


class TestClaudeCodeConversationHistoryServiceSessionExpiration:
    """Test session expiration handling in ClaudeCodeConversationHistoryService."""

    @pytest.fixture
    def mock_role(self):
        """Create mock role."""
        return MockAgentRole()

    @pytest.fixture
    def conversation(self, db_session: Session) -> Conversation:
        """Create a test conversation with an external session ID."""
        conversation_repo = ConversationRepository(db_session)
        conversation = conversation_repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=1,
            agent_role=AgentRoleType.PROJECT,
            engine=AgentEngine.CLAUDE_CODE,
            model_id=None,
            is_active=True,
        )
        # Set an external session ID to simulate an existing session
        conversation.external_session_id = "test-session-id-12345"
        db_session.commit()
        return conversation

    @pytest.fixture
    def conversation_repo(self, db_session: Session) -> ConversationRepository:
        """Create conversation repository."""
        return ConversationRepository(db_session)

    @pytest.fixture
    def history_service(self, conversation_repo, conversation):
        """Create ClaudeCodeConversationHistoryService instance."""
        return ClaudeCodeConversationHistoryService(
            conversation=conversation,
            conversation_repository=conversation_repo,
        )

    @pytest.fixture
    def execution_service(self, mock_role, conversation_repo, conversation, history_service, mock_agent_config_service):
        """Create ClaudeCodeAgentExecutionService instance."""
        return ClaudeCodeAgentExecutionService(
            conversation=conversation,
            role=mock_role,
            conversation_repository=conversation_repo,
            history_service=history_service,
            agent_config_service=mock_agent_config_service,
        )

    @pytest.mark.asyncio
    async def test_get_conversation_messages_session_expired(self, history_service, conversation, db_session):
        """Test that get_conversation_messages handles FileNotFoundError gracefully."""
        # Verify the session ID is set
        assert conversation.external_session_id == "test-session-id-12345"

        # Mock load_session_messages to raise FileNotFoundError
        with patch(
            "devboard.agents.engines.claude_code.conversation_history.ClaudeCodeSessionService"
        ) as mock_session_service_class:
            mock_session_service = Mock()
            mock_session_service.load_session_messages.side_effect = FileNotFoundError("Session file not found")
            mock_session_service_class.return_value = mock_session_service

            # Call get_conversation_messages
            events = await history_service.get_conversation_messages()

        # Verify a SESSION_EXPIRED event is returned
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "system"
        assert event.type == SystemEventType.SESSION_EXPIRED
        assert event.data["message"] == "Claude session was cleaned up, starting new conversation"

        # Verify the session ID was reset
        db_session.refresh(conversation)
        assert conversation.external_session_id is None

    @pytest.mark.asyncio
    async def test_get_conversation_messages_no_session_id(self, conversation_repo, db_session):
        """Test that get_conversation_messages returns empty list when no session ID."""
        # Create conversation without external session ID
        conversation = conversation_repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=2,
            agent_role=AgentRoleType.PROJECT,
            engine=AgentEngine.CLAUDE_CODE,
            model_id=None,
            is_active=True,
        )
        db_session.commit()

        history_service = ClaudeCodeConversationHistoryService(
            conversation=conversation,
            conversation_repository=conversation_repo,
        )

        events = await history_service.get_conversation_messages()
        assert events == []

    @pytest.mark.asyncio
    async def test_stream_events_session_expired(self, execution_service, conversation, db_session, monkeypatch):
        """Test that stream_events_for_message_or_approval handles FileNotFoundError gracefully."""
        # Verify the session ID is set
        assert conversation.external_session_id == "test-session-id-12345"

        # Create a mock agent that raises FileNotFoundError when streaming
        async def mock_stream_events_raise_fnf(_message_or_approvals):
            # Yield one event before raising to simulate partial streaming
            yield TextMessage(
                role=MessageRole.AGENT,
                text_content="Starting...",
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            raise FileNotFoundError("Session file not found")

        mock_agent = Mock()
        mock_agent.session_id = "test-session-id-12345"
        mock_agent.stream_events = mock_stream_events_raise_fnf

        # Patch _get_agent to return our mock
        monkeypatch.setattr(execution_service, "_get_agent", lambda extra_tools=None: mock_agent)

        # Collect all streamed events
        events = []
        async for event in execution_service.stream_events_for_message_or_approval("Test message"):
            events.append(event)

        # Verify we got the initial event and then the SESSION_EXPIRED event
        assert len(events) == 2

        # First event is the text message before the error
        assert events[0].event_type == "message"
        assert events[0].text_content == "Starting..."

        # Second event is the SESSION_EXPIRED system event
        assert events[1].event_type == "system"
        assert events[1].type == SystemEventType.SESSION_EXPIRED
        assert events[1].data["message"] == "Claude session was cleaned up, starting new conversation"

        # Verify the session ID was reset
        db_session.refresh(conversation)
        assert conversation.external_session_id is None

    @pytest.mark.asyncio
    async def test_stream_events_session_expired_immediate(
        self, execution_service, conversation, db_session, monkeypatch
    ):
        """Test FileNotFoundError raised immediately in stream_events."""
        # Verify the session ID is set
        assert conversation.external_session_id == "test-session-id-12345"

        # Create a mock agent that raises FileNotFoundError immediately
        async def mock_stream_events_raise_fnf_immediate(_message_or_approvals):
            raise FileNotFoundError("Session file not found")
            yield  # Make it a generator (type: ignore - unreachable code by design)

        mock_agent = Mock()
        mock_agent.session_id = "test-session-id-12345"
        mock_agent.stream_events = mock_stream_events_raise_fnf_immediate

        # Patch _get_agent to return our mock
        monkeypatch.setattr(execution_service, "_get_agent", lambda extra_tools=None: mock_agent)

        # Collect all streamed events
        events = []
        async for event in execution_service.stream_events_for_message_or_approval("Test message"):
            events.append(event)

        # Verify only the SESSION_EXPIRED event is returned
        assert len(events) == 1
        assert events[0].event_type == "system"
        assert events[0].type == SystemEventType.SESSION_EXPIRED

        # Verify the session ID was reset
        db_session.refresh(conversation)
        assert conversation.external_session_id is None


class TestSessionMessagesToEvents:
    """Test session_messages_to_events tool name normalization."""

    def _make_session_message(self, tool_name: str) -> AssistantSessionMessage:
        return AssistantSessionMessage(
            uuid="test-uuid",
            timestamp=datetime.datetime.now(datetime.UTC),
            line_num=1,
            is_sidechain=False,
            content=[{"type": "tool_use", "id": "tool-call-1", "name": tool_name, "input": {"arg": "value"}}],
        )

    def test_tool_use_block_normalizes_mcp_prefix(self):
        builtin_msg = self._make_session_message("mcp__builtin_tools__render_html")
        external_msg = self._make_session_message("mcp__github__create_issue")

        events = session_messages_to_events([builtin_msg, external_msg])

        assert len(events) == 2
        assert isinstance(events[0], ToolCall)
        assert events[0] == ToolCall(
            tool_call_id="tool-call-1",
            tool_name="render_html",
            tool_args={"arg": "value"},
            timestamp=builtin_msg.timestamp,
            uuid="test-uuid",
        )
        assert isinstance(events[1], ToolCall)
        assert events[1] == ToolCall(
            tool_call_id="tool-call-1",
            tool_name="mcp__github__create_issue",
            tool_args={"arg": "value"},
            timestamp=external_msg.timestamp,
            uuid="test-uuid",
        )


class TestMetaMessageEvents:
    """Test MetaMessage event emission from session_messages_to_events."""

    _TIMESTAMP = datetime.datetime(2025, 10, 8, 15, 0, 0, tzinfo=datetime.UTC)

    def _base_kwargs(self) -> dict:
        return {"uuid": "test-uuid", "timestamp": self._TIMESTAMP, "line_num": 1, "is_sidechain": False}

    def test_compact_summary_emits_meta_message(self):
        """MetaSessionMessage with COMPACT_SUMMARY produces a MetaMessage event."""
        session_msg = MetaSessionMessage(
            **self._base_kwargs(),
            meta_type=MetaMessageType.COMPACT_SUMMARY,
            text_content="Summary of conversation so far...",
        )

        events = session_messages_to_events([session_msg])

        assert len(events) == 1
        assert events[0] == MetaMessage(
            meta_type=MetaMessageType.COMPACT_SUMMARY,
            text_content="Summary of conversation so far...",
            timestamp=self._TIMESTAMP,
            uuid="test-uuid",
        )

    def test_skill_content_emits_meta_message(self):
        """MetaSessionMessage with SKILL_CONTENT produces a MetaMessage event."""
        session_msg = MetaSessionMessage(
            **self._base_kwargs(),
            meta_type=MetaMessageType.SKILL_CONTENT,
            text_content="Skill prompt content...",
        )

        events = session_messages_to_events([session_msg])

        assert len(events) == 1
        assert events[0] == MetaMessage(
            meta_type=MetaMessageType.SKILL_CONTENT,
            text_content="Skill prompt content...",
            timestamp=self._TIMESTAMP,
            uuid="test-uuid",
        )

    def test_regular_message_not_affected(self):
        """Regular UserSessionMessage still produces a TextMessage."""
        session_msg = UserSessionMessage(
            **self._base_kwargs(),
            content=[{"type": "text", "text": "Hello, can you help me?"}],
        )

        events = session_messages_to_events([session_msg])

        assert len(events) == 1
        assert events[0] == TextMessage(
            role=MessageRole.USER,
            text_content="Hello, can you help me?",
            timestamp=self._TIMESTAMP,
            uuid="test-uuid",
        )
