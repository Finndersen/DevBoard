"""Tests for AgentExecutionService base class."""

import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.agent_execution import AgentExecutionService
from devboard.agents.events import SystemEvent, SystemEventType
from devboard.mcp.mcp_tool_factory import MCPServerSetupFailure


class ConcreteAgentExecution(AgentExecutionService):
    """Concrete subclass for testing the base class template method."""

    async def _stream_events_impl(self, message_or_approvals, extra_tools):
        yield  # no-op: we only test the MCP setup failure path


class TestAgentExecutionMCPSetupFailures:
    def _build_service(self):
        conversation = Mock()
        conversation.id = 1
        conversation.engine.value = "internal"
        conversation.agent_role = "project_qa"

        role = Mock()
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
        )

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

        with patch("devboard.agents.agent_execution.MCPToolFactory", return_value=mock_factory):
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

        with patch("devboard.agents.agent_execution.MCPToolFactory", return_value=mock_factory):
            events = []
            async for event in service.stream_events_for_message_or_approval("hello"):
                events.append(event)

        error_events = [e for e in events if isinstance(e, SystemEvent) and e.type == SystemEventType.STREAM_ERROR]
        assert len(error_events) == 0
