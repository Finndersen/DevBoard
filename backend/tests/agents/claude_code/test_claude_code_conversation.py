"""Tests for ClaudeCodeConversationService session expiration handling."""

import datetime
from unittest.mock import Mock, patch

import pytest
from pydantic_ai import Tool
from sqlalchemy.orm import Session

from devboard.agents.engines import AgentEngine
from devboard.agents.engines.claude_code.agent_conversation import ClaudeCodeConversationService
from devboard.agents.events import MessageRole, SystemEventType, TextMessage
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


class TestClaudeCodeConversationServiceSessionExpiration:
    """Test session expiration handling in ClaudeCodeConversationService."""

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
    def service(self, mock_role, conversation_repo, conversation):
        """Create ClaudeCodeConversationService instance."""
        return ClaudeCodeConversationService(
            conversation=conversation,
            role=mock_role,
            conversation_repository=conversation_repo,
        )

    @pytest.mark.asyncio
    async def test_get_conversation_messages_session_expired(self, service, conversation, db_session):
        """Test that get_conversation_messages handles FileNotFoundError gracefully."""
        # Verify the session ID is set
        assert conversation.external_session_id == "test-session-id-12345"

        # Mock load_session_messages to raise FileNotFoundError
        with patch(
            "devboard.agents.engines.claude_code.agent_conversation.ClaudeCodeSessionService"
        ) as mock_session_service_class:
            mock_session_service = Mock()
            mock_session_service.load_session_messages.side_effect = FileNotFoundError("Session file not found")
            mock_session_service_class.return_value = mock_session_service

            # Call get_conversation_messages
            events = await service.get_conversation_messages()

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
    async def test_get_conversation_messages_no_session_id(self, mock_role, conversation_repo, db_session):
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

        service = ClaudeCodeConversationService(
            conversation=conversation,
            role=mock_role,
            conversation_repository=conversation_repo,
        )

        events = await service.get_conversation_messages()
        assert events == []

    @pytest.mark.asyncio
    async def test_stream_events_session_expired(self, service, conversation, db_session, monkeypatch):
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
        monkeypatch.setattr(service, "_get_agent", lambda: mock_agent)

        # Collect all streamed events
        events = []
        async for event in service.stream_events_for_message_or_approval("Test message"):
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
    async def test_stream_events_session_expired_immediate(self, service, conversation, db_session, monkeypatch):
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
        monkeypatch.setattr(service, "_get_agent", lambda: mock_agent)

        # Collect all streamed events
        events = []
        async for event in service.stream_events_for_message_or_approval("Test message"):
            events.append(event)

        # Verify only the SESSION_EXPIRED event is returned
        assert len(events) == 1
        assert events[0].event_type == "system"
        assert events[0].type == SystemEventType.SESSION_EXPIRED

        # Verify the session ID was reset
        db_session.refresh(conversation)
        assert conversation.external_session_id is None
