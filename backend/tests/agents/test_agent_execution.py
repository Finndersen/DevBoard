"""Tests for AgentExecutionService base class."""

import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.events import (
    AgentRunCompletedEvent,
    AgentRunStartedEvent,
    ContextUsage,
    MessageRole,
    SystemEvent,
    SystemEventType,
    TextMessage,
)
from devboard.agents.exceptions import AgentInterruptedError
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
        if False:
            yield  # make this an async generator without yielding anything


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

        error_events = [e for e in events if isinstance(e, SystemEvent) and e.sub_type == SystemEventType.STREAM_ERROR]
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

        error_events = [e for e in events if isinstance(e, SystemEvent) and e.sub_type == SystemEventType.STREAM_ERROR]
        assert len(error_events) == 0


def _make_patched_factory():
    """Return a mock MCPToolFactory context manager with no failures or tools."""
    mock_factory = Mock()
    mock_factory.setup_failures = []
    mock_factory.get_tools.return_value = []
    mock_factory.__aenter__ = AsyncMock(return_value=mock_factory)
    mock_factory.__aexit__ = AsyncMock(return_value=False)
    return mock_factory


class TestAgentExecutionLifecycleEvents:
    """Tests for AgentRunStartedEvent / AgentRunCompletedEvent emission in stream_events_for_message_or_approval."""

    @pytest.mark.asyncio
    async def test_happy_path_starts_and_completes(self):
        """First event is AgentRunStartedEvent; last is AgentRunCompletedEvent(status='completed')."""
        service = _make_concrete_service()

        with patch("devboard.agents.execution.agent_execution.MCPToolFactory", return_value=_make_patched_factory()):
            events = []
            async for event in service.stream_events_for_message_or_approval("hello"):
                events.append(event)

        assert len(events) == 2
        assert isinstance(events[0], AgentRunStartedEvent)
        assert events[0].conversation_id == 1
        assert isinstance(events[1], AgentRunCompletedEvent)
        assert events[1].status == "completed"
        assert events[1].error is None

    @pytest.mark.asyncio
    async def test_interrupted_yields_completed_then_reraises(self):
        """On AgentInterruptedError: AgentRunCompletedEvent(status='interrupted') is yielded, then error is re-raised."""

        class InterruptingService(AgentExecutionService):
            async def _run_impl(self, message, extra_tools):
                raise NotImplementedError

            async def _stream_events_impl(self, message_or_approvals, extra_tools):
                raise AgentInterruptedError("stopped")
                yield  # make this an async generator

        service = InterruptingService(
            conversation=_make_concrete_service().conversation,
            role=Mock(),
            conversation_repository=Mock(),
            history_service=Mock(),
            agent_config_service=_make_concrete_service()._agent_config_service,
            working_dir="/test",
        )

        with patch("devboard.agents.execution.agent_execution.MCPToolFactory", return_value=_make_patched_factory()):
            events = []
            with pytest.raises(AgentInterruptedError):
                async for event in service.stream_events_for_message_or_approval("hello"):
                    events.append(event)

        assert len(events) == 2
        assert isinstance(events[0], AgentRunStartedEvent)
        assert isinstance(events[1], AgentRunCompletedEvent)
        assert events[1].status == "interrupted"
        assert events[1].error is None

    @pytest.mark.asyncio
    async def test_generic_exception_yields_failed_then_reraises(self):
        """On generic Exception: AgentRunCompletedEvent(status='failed', error=...) is yielded, then re-raised."""

        class FailingService(AgentExecutionService):
            async def _run_impl(self, message, extra_tools):
                raise NotImplementedError

            async def _stream_events_impl(self, message_or_approvals, extra_tools):
                raise RuntimeError("something broke")
                yield  # make this an async generator

        service = FailingService(
            conversation=_make_concrete_service().conversation,
            role=Mock(),
            conversation_repository=Mock(),
            history_service=Mock(),
            agent_config_service=_make_concrete_service()._agent_config_service,
            working_dir="/test",
        )

        with patch("devboard.agents.execution.agent_execution.MCPToolFactory", return_value=_make_patched_factory()):
            events = []
            with pytest.raises(RuntimeError, match="something broke"):
                async for event in service.stream_events_for_message_or_approval("hello"):
                    events.append(event)

        assert len(events) == 2
        assert isinstance(events[0], AgentRunStartedEvent)
        assert isinstance(events[1], AgentRunCompletedEvent)
        assert events[1].status == "failed"
        assert events[1].error == "something broke"

    @pytest.mark.asyncio
    async def test_early_termination_no_runtime_error(self):
        """Consumer calling .aclose() after AgentRunStartedEvent does not raise RuntimeError."""
        service = _make_concrete_service()

        with patch("devboard.agents.execution.agent_execution.MCPToolFactory", return_value=_make_patched_factory()):
            gen = service.stream_events_for_message_or_approval("hello")
            first_event = await gen.__anext__()
            assert isinstance(first_event, AgentRunStartedEvent)

            # Close the generator early — must not raise RuntimeError
            await gen.aclose()


class TestContextUsageHandling:
    """Tests for ContextUsage interception from engine streams."""

    @pytest.mark.asyncio
    async def test_context_usage_intercepted_and_not_re_yielded(self):
        """ContextUsage yielded by engine is intercepted; not visible in output stream."""

        class UsageYieldingService(AgentExecutionService):
            async def _run_impl(self, message, extra_tools):
                raise NotImplementedError

            async def _stream_events_impl(self, message_or_approvals, extra_tools):
                yield TextMessage(
                    role=MessageRole.AGENT,
                    text_content="Response",
                    timestamp=datetime.datetime.now(datetime.UTC),
                )
                yield ContextUsage(
                    input_tokens=100,
                    output_tokens=50,
                    cache_read_tokens=800,
                    cache_write_tokens=200,
                    cost_usd=0.005,
                )

        service = UsageYieldingService(
            conversation=_make_concrete_service().conversation,
            role=Mock(),
            conversation_repository=Mock(),
            history_service=Mock(),
            agent_config_service=_make_concrete_service()._agent_config_service,
            working_dir="/test",
        )

        with patch("devboard.agents.execution.agent_execution.MCPToolFactory", return_value=_make_patched_factory()):
            events = []
            async for event in service.stream_events_for_message_or_approval("hello"):
                events.append(event)

        # ContextUsage must not appear in the output stream
        assert not any(isinstance(e, ContextUsage) for e in events)
        # AgentRunCompletedEvent must carry the usage
        completed = next(e for e in events if isinstance(e, AgentRunCompletedEvent))
        assert completed.usage is not None
        assert completed.usage.input_tokens == 100
        assert completed.usage.output_tokens == 50
        assert completed.usage.cost_usd == 0.005

    @pytest.mark.asyncio
    async def test_context_usage_none_when_interrupted_before_yield(self):
        """AgentRunCompletedEvent.usage is None when engine raises before yielding ContextUsage."""

        class InterruptBeforeUsageService(AgentExecutionService):
            async def _run_impl(self, message, extra_tools):
                raise NotImplementedError

            async def _stream_events_impl(self, message_or_approvals, extra_tools):
                raise AgentInterruptedError("stopped before usage")
                yield  # make this an async generator

        service = InterruptBeforeUsageService(
            conversation=_make_concrete_service().conversation,
            role=Mock(),
            conversation_repository=Mock(),
            history_service=Mock(),
            agent_config_service=_make_concrete_service()._agent_config_service,
            working_dir="/test",
        )

        with patch("devboard.agents.execution.agent_execution.MCPToolFactory", return_value=_make_patched_factory()):
            events = []
            with pytest.raises(AgentInterruptedError):
                async for event in service.stream_events_for_message_or_approval("hello"):
                    events.append(event)

        completed = next(e for e in events if isinstance(e, AgentRunCompletedEvent))
        assert completed.status == "interrupted"
        assert completed.usage is None
