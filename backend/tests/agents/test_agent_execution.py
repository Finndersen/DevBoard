"""Tests for AgentExecutionService base class."""

import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.events import SystemEvent, SystemEventType
from devboard.agents.execution.agent_execution import AgentExecutionService
from devboard.mcp.mcp_tool_factory import MCPServerSetupFailure


def _make_concrete_service() -> "ConcreteAgentExecution":
    """Build a ConcreteAgentExecution with standard mocked dependencies."""
    conversation = Mock()
    conversation.id = 1
    conversation.engine.value = "internal"
    conversation.agent_role = "project_qa"

    role = Mock()
    role.get_context_content = AsyncMock(return_value="test context content")

    conversation_repo = Mock()
    history_service = Mock()
    agent_config_service = Mock()
    agent_config_service.get_enabled_mcp_tools.return_value = []

    return ConcreteAgentExecution(
        conversation=conversation,
        role=role,
        conversation_repository=conversation_repo,
        history_service=history_service,
        agent_config_service=agent_config_service,
        working_dir="/test/working_dir",
    )


class ConcreteAgentExecution(AgentExecutionService):
    """Concrete subclass for testing the base class template method."""

    async def _run_impl(self, message, extra_tools):
        raise NotImplementedError  # not tested here

    async def _stream_events_impl(self, message_or_approvals, extra_tools):
        yield  # no-op: we only test the MCP setup failure path


class TestBuildContextMessage:
    """Tests for AgentExecutionService._build_context_message()."""

    @pytest.mark.asyncio
    async def test_wraps_context_in_system_message_tag(self):
        """Context should be wrapped in a system_message block and prepended."""
        service = _make_concrete_service()

        result = await service._build_context_message("Hello agent")

        assert '<system_message type="initial_context">' in result
        assert "test context content" in result
        assert result.endswith("Hello agent")

    @pytest.mark.asyncio
    async def test_context_precedes_user_message(self):
        """Context block should appear before the user message."""
        service = _make_concrete_service()

        result = await service._build_context_message("User question")

        context_pos = result.index("<system_message")
        message_pos = result.index("User question")
        assert context_pos < message_pos


class TestAgentExecutionMCPSetupFailures:
    def _build_service(self):
        return _make_concrete_service()

    @pytest.mark.asyncio
    async def test_yields_stream_error_events_for_mcp_setup_failures(self):
        """stream_events_for_message_or_approval should yield STREAM_ERROR events for each MCP setup failure."""
        service = self._build_service()

        failures = [
            MCPServerSetupFailure(server_name="Server A", server_id=1, error="Connection refused"),
            MCPServerSetupFailure(server_name="Server B", server_id=2, error="Auth failed"),
        ]

        mock_factory = Mock()
        mock_factory.setup_failures = failures
        mock_factory.get_tools.return_value = []
        mock_factory.__aenter__ = AsyncMock(return_value=mock_factory)
        mock_factory.__aexit__ = AsyncMock(return_value=False)

        with patch("devboard.agents.execution.agent_execution.MCPToolFactory", return_value=mock_factory):
            events = []
            async for event in service.stream_events_for_message_or_approval("hello"):
                events.append(event)

        error_events = [e for e in events if isinstance(e, SystemEvent) and e.type == SystemEventType.STREAM_ERROR]
        assert len(error_events) == 2

        assert error_events[0].data == {
            "error_code": "MCP_SERVER_SETUP_FAILED",
            "message": "MCP server 'Server A' failed to connect: Connection refused",
        }
        assert error_events[1].data == {
            "error_code": "MCP_SERVER_SETUP_FAILED",
            "message": "MCP server 'Server B' failed to connect: Auth failed",
        }
        assert isinstance(error_events[0].timestamp, datetime.datetime)

    @pytest.mark.asyncio
    async def test_no_error_events_when_no_setup_failures(self):
        """No STREAM_ERROR events should be yielded when all MCP servers connect successfully."""
        service = self._build_service()

        mock_factory = Mock()
        mock_factory.setup_failures = []
        mock_factory.get_tools.return_value = []
        mock_factory.__aenter__ = AsyncMock(return_value=mock_factory)
        mock_factory.__aexit__ = AsyncMock(return_value=False)

        with patch("devboard.agents.execution.agent_execution.MCPToolFactory", return_value=mock_factory):
            events = []
            async for event in service.stream_events_for_message_or_approval("hello"):
                events.append(event)

        error_events = [e for e in events if isinstance(e, SystemEvent) and e.type == SystemEventType.STREAM_ERROR]
        assert len(error_events) == 0
