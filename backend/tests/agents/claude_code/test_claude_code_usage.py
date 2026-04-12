"""Tests for Claude Code context usage extraction."""

import datetime
from unittest.mock import Mock

import pytest
from claude_agent_sdk import ResultMessage
from pydantic_ai import Tool
from sqlalchemy.orm import Session

from devboard.agents.engines import AgentEngine
from devboard.agents.engines.claude_code import ClaudeCodeAgentExecutionService
from devboard.agents.engines.claude_code.agent import ClaudeCodeAgent
from devboard.agents.events import ContextUsage, MessageRole, SystemEventType, TextMessage
from devboard.agents.roles import AgentRole, AgentRoleType
from devboard.db.models import Conversation, ParentEntityType
from devboard.db.repositories.conversation import ConversationRepository


class MockAgentRole(AgentRole):
    def get_system_prompt(self) -> str:
        return "Test system prompt"

    def get_tools(self) -> list[Tool]:
        return []

    async def get_context_content(self) -> str:
        return "Test context"


def _make_result_message(usage: dict | None = None, total_cost_usd: float | None = None) -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=1000,
        duration_api_ms=900,
        is_error=False,
        num_turns=1,
        session_id="test-session",
        usage=usage,
        total_cost_usd=total_cost_usd,
    )


class TestClaudeCodeAgentGetContextUsage:
    """Tests for ClaudeCodeAgent.get_context_usage()."""

    @pytest.fixture
    def agent(self):
        role = MockAgentRole()
        return ClaudeCodeAgent(role=role, model=None, session_id="test-session")

    def test_returns_none_when_no_result_message(self, agent):
        assert agent.last_result_message is None
        assert agent.get_context_usage() is None

    def test_returns_none_when_result_message_has_no_usage(self, agent):
        agent.last_result_message = _make_result_message(usage=None)
        assert agent.get_context_usage() is None

    def test_extracts_usage_fields(self, agent):
        agent.last_result_message = _make_result_message(
            usage={
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 800,
                "cache_creation_input_tokens": 200,
            },
            total_cost_usd=0.012,
        )

        usage = agent.get_context_usage()

        assert usage is not None
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_tokens == 800
        assert usage.cache_write_tokens == 200
        assert usage.cost_usd == 0.012

    def test_extracts_usage_without_cost(self, agent):
        agent.last_result_message = _make_result_message(
            usage={
                "input_tokens": 300,
                "output_tokens": 80,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 500,
            }
        )

        usage = agent.get_context_usage()

        assert usage is not None
        assert usage.input_tokens == 300
        assert usage.output_tokens == 80
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 500
        assert usage.cost_usd is None

    def test_missing_usage_keys_default_to_zero(self, agent):
        agent.last_result_message = _make_result_message(usage={"output_tokens": 42})

        usage = agent.get_context_usage()

        assert usage is not None
        assert usage.input_tokens == 0
        assert usage.output_tokens == 42
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0


class TestClaudeCodeExecutionServiceUsage:
    """Tests for usage propagation in ClaudeCodeAgentExecutionService via AgentRunCompletedEvent."""

    @pytest.fixture
    def conversation(self, db_session: Session) -> Conversation:
        repo = ConversationRepository(db_session)
        conv = repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=1,
            agent_role=AgentRoleType.PROJECT,
            engine=AgentEngine.CLAUDE_CODE,
            model_id=None,
            is_active=True,
        )
        conv.external_session_id = "test-session-id"
        db_session.commit()
        return conv

    @pytest.fixture
    def execution_service(self, conversation, db_session, mock_agent_config_service):
        repo = ConversationRepository(db_session)
        role = MockAgentRole()
        return ClaudeCodeAgentExecutionService(
            conversation=conversation,
            role=role,
            conversation_repository=repo,
            history_service=Mock(),
            agent_config_service=mock_agent_config_service,
            working_dir="/test/dir",
        )

    @pytest.mark.asyncio
    async def test_usage_on_completed_event_after_successful_stream(self, execution_service, monkeypatch):
        """AgentRunCompletedEvent carries usage from agent.get_context_usage() after stream completes."""
        from devboard.agents.events import AgentRunCompletedEvent

        expected_usage = ContextUsage(
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=800,
            cache_write_tokens=200,
            cost_usd=0.005,
        )

        async def mock_stream_events(_msg_or_approvals, **kwargs):
            yield TextMessage(
                role=MessageRole.AGENT,
                text_content="Hello!",
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        mock_agent = Mock()
        mock_agent.session_id = "test-session-id"
        mock_agent.stream_events = mock_stream_events
        mock_agent.get_context_usage.return_value = expected_usage

        monkeypatch.setattr(execution_service, "_get_agent", lambda extra_tools=None: mock_agent)

        events = []
        async for event in execution_service.stream_events_for_message_or_approval("Test message"):
            events.append(event)

        completed = next(e for e in events if isinstance(e, AgentRunCompletedEvent))
        assert completed.usage == expected_usage
        mock_agent.get_context_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_usage_none_on_completed_event_when_agent_has_no_usage(self, execution_service, monkeypatch):
        """AgentRunCompletedEvent.usage is None when agent.get_context_usage() returns None."""
        from devboard.agents.events import AgentRunCompletedEvent

        async def mock_stream_events(_msg_or_approvals, **kwargs):
            yield TextMessage(
                role=MessageRole.AGENT,
                text_content="Done.",
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        mock_agent = Mock()
        mock_agent.session_id = "test-session-id"
        mock_agent.stream_events = mock_stream_events
        mock_agent.get_context_usage.return_value = None

        monkeypatch.setattr(execution_service, "_get_agent", lambda extra_tools=None: mock_agent)

        events = []
        async for event in execution_service.stream_events_for_message_or_approval("Test message"):
            events.append(event)

        completed = next(e for e in events if isinstance(e, AgentRunCompletedEvent))
        assert completed.usage is None

    @pytest.mark.asyncio
    async def test_usage_not_set_on_file_not_found_error(self, execution_service, monkeypatch):
        """AgentRunCompletedEvent.usage is None when streaming fails with FileNotFoundError."""
        from devboard.agents.events import AgentRunCompletedEvent

        async def mock_stream_events_raise(_msg_or_approvals, **kwargs):
            raise FileNotFoundError("Session not found")
            yield  # noqa: unreachable

        mock_agent = Mock()
        mock_agent.session_id = "test-session-id"
        mock_agent.stream_events = mock_stream_events_raise
        mock_agent.get_context_usage.return_value = ContextUsage(
            input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0
        )

        monkeypatch.setattr(execution_service, "_get_agent", lambda extra_tools=None: mock_agent)

        events = []
        async for event in execution_service.stream_events_for_message_or_approval("Test message"):
            events.append(event)

        # get_context_usage should NOT be called since FileNotFoundError was raised before the yield
        mock_agent.get_context_usage.assert_not_called()
        completed = next(e for e in events if isinstance(e, AgentRunCompletedEvent))
        assert completed.usage is None
        # Should have SESSION_EXPIRED event
        assert any(e.event_type == "system" and e.sub_type == SystemEventType.SESSION_EXPIRED for e in events)
