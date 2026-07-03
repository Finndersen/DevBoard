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
from devboard.db.models.enums import EntityType
from devboard.mcp.mcp_tool_factory import MCPServerSetupFailure


def _make_log_entry(
    *,
    type: str = "task.merged",
    content: str = "A task was merged",
    task_id: int | None = None,
    project_id: int | None = None,
    entry_metadata: dict | None = None,
) -> Mock:
    """Build a mock LogEntry."""
    entry = Mock()
    entry.type = type
    entry.content = content
    entry.task_id = task_id
    entry.project_id = project_id
    entry.entry_metadata = entry_metadata
    entry.timestamp = datetime.datetime(2026, 1, 15, 10, 0, 0, tzinfo=datetime.UTC)
    return entry


def _make_concrete_service(
    *,
    event_context_types: list[str] | None = None,
    log_entry_repo: Mock | None = None,
    parent_entity_type: EntityType = EntityType.PROJECT,
    parent_entity_id: int = 42,
    conversation_id: int = 1,
    last_activity_at: datetime.datetime | None = None,
    created_at: datetime.datetime | None = None,
) -> "ConcreteAgentExecution":
    """Build a ConcreteAgentExecution with standard mocked dependencies."""
    conversation = Mock()
    conversation.id = conversation_id
    conversation.engine.value = "internal"
    conversation.agent_role = "project_qa"
    conversation.parent_entity_type = parent_entity_type
    conversation.parent_entity_id = parent_entity_id
    conversation.last_activity_at = last_activity_at
    conversation.created_at = created_at or datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)

    role = Mock()
    role.get_context_content = AsyncMock(return_value="test context content")
    role.event_context_types = event_context_types if event_context_types is not None else []

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
        log_entry_repo=log_entry_repo,
    )


class ConcreteAgentExecution(AgentExecutionService):
    """Concrete subclass for testing the base class template method."""

    async def _run_impl(self, message, extra_tools):
        raise NotImplementedError  # not tested here

    async def _stream_events_impl(self, message_or_approvals, extra_tools):
        if False:
            yield  # make this an async generator without yielding anything


class TestEnrichMessage:
    """Tests for AgentExecutionService._enrich_message()."""

    @pytest.mark.asyncio
    async def test_first_message_includes_initial_context(self):
        """First message should include initial_context system_message block."""
        service = _make_concrete_service()

        result = await service._enrich_message("Hello agent", is_first_message=True)

        assert '<system_message type="initial_context">' in result
        assert "test context content" in result
        assert result.endswith("Hello agent")

    @pytest.mark.asyncio
    async def test_non_first_message_excludes_initial_context(self):
        """Non-first messages should not include initial_context."""
        service = _make_concrete_service()

        result = await service._enrich_message("Follow-up", is_first_message=False)

        assert "initial_context" not in result
        assert result == "Follow-up"

    @pytest.mark.asyncio
    async def test_context_precedes_user_message(self):
        """Context block should appear before the user message text."""
        service = _make_concrete_service()

        result = await service._enrich_message("User question", is_first_message=True)

        context_pos = result.index("<system_message")
        message_pos = result.index("User question")
        assert context_pos < message_pos

    @pytest.mark.asyncio
    async def test_no_event_context_when_role_has_empty_types(self):
        """No event_context block injected when role.event_context_types is empty."""
        log_entry_repo = Mock()
        service = _make_concrete_service(event_context_types=[], log_entry_repo=log_entry_repo)

        result = await service._enrich_message("Hello", is_first_message=False)

        log_entry_repo.query.assert_not_called()
        assert "event_context" not in result

    @pytest.mark.asyncio
    async def test_no_event_context_when_log_entry_repo_is_none(self):
        """No event_context block injected when log_entry_repo is not provided."""
        service = _make_concrete_service(event_context_types=["task.merged"], log_entry_repo=None)

        result = await service._enrich_message("Hello", is_first_message=False)

        assert "event_context" not in result

    @pytest.mark.asyncio
    async def test_event_context_injected_for_project_conversation(self):
        """event_context block is injected for project conversations with matching events."""
        entry = _make_log_entry(type="task.created", content="Task Alpha was created")
        log_entry_repo = Mock()
        log_entry_repo.query.return_value = [entry]

        service = _make_concrete_service(
            event_context_types=["task.created"],
            log_entry_repo=log_entry_repo,
            parent_entity_type=EntityType.PROJECT,
            parent_entity_id=10,
        )

        result = await service._enrich_message("What's new?", is_first_message=False)

        log_entry_repo.query.assert_called_once_with(
            project_id=10,
            types=["task.created"],
            since=service.conversation.created_at,
        )
        assert '<system_message type="event_context">' in result
        assert "Task Alpha was created" in result
        assert result.endswith("What's new?")

    @pytest.mark.asyncio
    async def test_no_event_context_block_when_no_events_returned(self):
        """No event_context block is added when no events match."""
        log_entry_repo = Mock()
        log_entry_repo.query.return_value = []

        service = _make_concrete_service(
            event_context_types=["task.created"],
            log_entry_repo=log_entry_repo,
            parent_entity_type=EntityType.PROJECT,
            parent_entity_id=10,
        )

        result = await service._enrich_message("Hello", is_first_message=False)

        assert "event_context" not in result
        assert result == "Hello"

    @pytest.mark.asyncio
    async def test_self_originated_events_excluded(self):
        """Events with conversation_id matching the current conversation are excluded."""
        own_event = _make_log_entry(
            type="task.created",
            content="Own event",
            entry_metadata={"conversation_id": 1},
        )
        other_event = _make_log_entry(
            type="task.created",
            content="Other event",
            entry_metadata={"conversation_id": 99},
        )
        log_entry_repo = Mock()
        log_entry_repo.query.return_value = [own_event, other_event]

        service = _make_concrete_service(
            event_context_types=["task.created"],
            log_entry_repo=log_entry_repo,
            parent_entity_type=EntityType.PROJECT,
            parent_entity_id=10,
            conversation_id=1,
        )

        result = await service._enrich_message("Hello", is_first_message=False)

        assert "Own event" not in result
        assert "Other event" in result

    @pytest.mark.asyncio
    async def test_sibling_task_merged_includes_rebase_note(self):
        """task.merged events from sibling tasks include a rebase guidance note."""
        sibling_merged = _make_log_entry(
            type="task.merged",
            content="Task Beta was merged",
            task_id=99,  # different task
        )
        log_entry_repo = Mock()
        log_entry_repo.query.return_value = [sibling_merged]

        with patch("devboard.agents.execution.agent_execution.object_session") as mock_session:
            task_mock = Mock()
            task_mock.project_id = 5
            mock_session.return_value.get.return_value = task_mock

            service = _make_concrete_service(
                event_context_types=["task.merged"],
                log_entry_repo=log_entry_repo,
                parent_entity_type=EntityType.TASK,
                parent_entity_id=42,  # different from sibling task_id=99
            )

            result = await service._enrich_message("Continue working", is_first_message=False)

        assert "rebasing" in result.lower()
        assert "Task Beta was merged" in result

    @pytest.mark.asyncio
    async def test_own_task_merged_excludes_rebase_note(self):
        """task.merged events for the current task itself do not include the rebase note."""
        own_merged = _make_log_entry(
            type="task.merged",
            content="This task was merged",
            task_id=42,  # same as parent_entity_id
        )
        log_entry_repo = Mock()
        log_entry_repo.query.return_value = [own_merged]

        with patch("devboard.agents.execution.agent_execution.object_session") as mock_session:
            task_mock = Mock()
            task_mock.project_id = 5
            mock_session.return_value.get.return_value = task_mock

            service = _make_concrete_service(
                event_context_types=["task.merged"],
                log_entry_repo=log_entry_repo,
                parent_entity_type=EntityType.TASK,
                parent_entity_id=42,
            )

            result = await service._enrich_message("Check status", is_first_message=False)

        assert "This task was merged" in result
        assert "rebase" not in result.lower()

    @pytest.mark.asyncio
    async def test_uses_last_activity_at_as_since_when_available(self):
        """Uses last_activity_at as the time window start when set."""
        log_entry_repo = Mock()
        log_entry_repo.query.return_value = []
        last_activity = datetime.datetime(2026, 3, 1, 12, 0, 0, tzinfo=datetime.UTC)

        service = _make_concrete_service(
            event_context_types=["task.created"],
            log_entry_repo=log_entry_repo,
            parent_entity_type=EntityType.PROJECT,
            parent_entity_id=10,
            last_activity_at=last_activity,
        )

        await service._enrich_message("Hello", is_first_message=False)

        call_kwargs = log_entry_repo.query.call_args.kwargs
        assert call_kwargs["since"] == last_activity

    @pytest.mark.asyncio
    async def test_event_context_and_initial_context_ordering(self):
        """On first message with events: initial_context appears before event_context."""
        entry = _make_log_entry(type="task.created", content="Task created")
        log_entry_repo = Mock()
        log_entry_repo.query.return_value = [entry]

        service = _make_concrete_service(
            event_context_types=["task.created"],
            log_entry_repo=log_entry_repo,
            parent_entity_type=EntityType.PROJECT,
            parent_entity_id=10,
        )

        result = await service._enrich_message("Hello", is_first_message=True)

        initial_pos = result.index("initial_context")
        event_pos = result.index("event_context")
        user_pos = result.index("Hello")
        assert initial_pos < event_pos < user_pos


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
