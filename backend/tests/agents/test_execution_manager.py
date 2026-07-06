"""Tests for ConversationExecutionManager."""

import asyncio
import datetime
from typing import Literal
from unittest.mock import patch

import pytest

from devboard.agents.events import (
    AgentRunCompletedEvent,
    AgentRunStartedEvent,
    ContextUsage,
    MessageRole,
    MetaMessage,
    MetaMessageType,
    TextMessage,
)
from devboard.agents.exceptions import AgentInterruptedError, ConversationBusyError, SubAgentRateLimitError
from devboard.agents.execution.manager import ConversationExecutionManager
from devboard.agents.execution.types import ConversationExecution, ExecutionStatus
from devboard.agents.system_message_tags import wrap_system_message


@pytest.fixture
def manager() -> ConversationExecutionManager:
    """Return a fresh ConversationExecutionManager for each test."""
    return ConversationExecutionManager()


async def _push_started(q, conversation_id: int) -> None:
    """Push the AgentRunStartedEvent that _run_agent_for_conversation emits."""
    await q.put(
        (
            conversation_id,
            AgentRunStartedEvent(
                conversation_id=conversation_id,
                timestamp=datetime.datetime.now(datetime.UTC),
            ),
        )
    )


async def _push_complete(
    q,
    conversation_id: int,
    status: Literal["completed", "interrupted", "failed"] = "completed",
    error: str | None = None,
    usage: ContextUsage | None = None,
) -> None:
    """Push the AgentRunCompletedEvent that _run_agent_for_conversation emits in its finally."""
    await q.put(
        (
            conversation_id,
            AgentRunCompletedEvent(
                status=status,
                error=error,
                usage=usage,
                timestamp=datetime.datetime.now(datetime.UTC),
            ),
        )
    )


async def _simple_coro(q, ie, *, conversation_id, message_or_approvals, **kwargs) -> None:
    await _push_started(q, conversation_id)
    await _push_complete(q, conversation_id)


async def _interrupt_raising_coro(q, ie, *, conversation_id, message_or_approvals, **kwargs) -> None:
    await _push_started(q, conversation_id)
    await _push_complete(q, conversation_id, status="interrupted")
    raise AgentInterruptedError("interrupted")


async def _error_raising_coro(q, ie, *, conversation_id, message_or_approvals, **kwargs) -> None:
    await _push_started(q, conversation_id)
    await _push_complete(q, conversation_id, status="failed", error="something went wrong")
    raise ValueError("something went wrong")


async def _event_pushing_coro(q, ie, *, conversation_id, message_or_approvals, **kwargs) -> None:
    await _push_started(q, conversation_id)
    event = TextMessage(
        event_type="message",
        role=MessageRole.AGENT,
        text_content="hello",
        timestamp=datetime.datetime.now(datetime.UTC),
    )
    await q.put((conversation_id, event))
    await _push_complete(q, conversation_id)


class TestStartAgentExecution:
    """Tests for ConversationExecutionManager.start_agent_execution()."""

    @pytest.mark.asyncio
    async def test_creates_running_execution(self, manager):
        """Starting an execution should create a RUNNING ConversationExecution."""
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_simple_coro):
            execution = manager.start_agent_execution(1, "Hello")

        assert isinstance(execution, ConversationExecution)
        assert execution.conversation_id == 1
        assert execution.status == ExecutionStatus.RUNNING
        assert not execution.interrupt_requested.is_set()
        assert isinstance(execution.started_at, datetime.datetime)
        assert execution.completed_at is None

        await execution.asyncio_task

    @pytest.mark.asyncio
    async def test_raises_conflict_if_already_running(self, manager):
        """Should raise ConversationBusyError if an execution is already active."""
        blocker = asyncio.Event()

        async def _blocking(q, ie, *, conversation_id, message_or_approvals, **kwargs):
            await blocker.wait()

        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_blocking):
            manager.start_agent_execution(1, "Hello")
            with pytest.raises(ConversationBusyError):
                manager.start_agent_execution(1, "Hello")

        blocker.set()

    @pytest.mark.asyncio
    async def test_allows_new_after_completion(self, manager):
        """Should allow a new execution after the previous one completes."""
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_simple_coro):
            first = manager.start_agent_execution(1, "Hello")
            await first.asyncio_task
            await asyncio.sleep(0.01)

            second = manager.start_agent_execution(1, "Hello")
            assert second is not first
            await second.asyncio_task


class TestExecutionLifecycle:
    """Tests for execution status transitions."""

    @pytest.mark.asyncio
    async def test_completed_status_on_success(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_simple_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task
        await asyncio.sleep(0.01)

        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_interrupted_status_on_agent_interrupted_error(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_interrupt_raising_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task
        await asyncio.sleep(0.01)

        assert execution.status == ExecutionStatus.INTERRUPTED
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_failed_status_on_generic_exception(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_error_raising_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task
        await asyncio.sleep(0.01)

        assert execution.status == ExecutionStatus.FAILED
        assert execution.error == "something went wrong"
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_agent_run_started_event_pushed_during_execution(self, manager):
        """_run_agent_for_conversation should push AgentRunStartedEvent onto the broadcast queue."""
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_simple_coro):
            execution = manager.start_agent_execution(1, "Hello")

        await execution.asyncio_task

        # AgentRunStartedEvent is pushed by the coroutine (before AgentRunCompletedEvent)
        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conversation_id == 1
        assert isinstance(event, AgentRunStartedEvent)
        assert event.conversation_id == 1

    @pytest.mark.asyncio
    async def test_execution_complete_event_pushed_on_completion(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_simple_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        # Drain the AgentRunStartedEvent first
        _, start_event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert isinstance(start_event, AgentRunStartedEvent)

        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conversation_id == 1
        assert isinstance(event, AgentRunCompletedEvent)
        assert event.status == "completed"
        assert event.error is None

    @pytest.mark.asyncio
    async def test_events_then_execution_complete_in_broadcast_queue(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_event_pushing_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        # Drain the AgentRunStartedEvent first
        _, start_event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert isinstance(start_event, AgentRunStartedEvent)

        conv_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conv_id == 1
        assert isinstance(event, TextMessage)

        conv_id, complete_event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conv_id == 1
        assert isinstance(complete_event, AgentRunCompletedEvent)

    @pytest.mark.asyncio
    async def test_execution_complete_event_includes_error_on_failure(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_error_raising_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        # Drain the AgentRunStartedEvent first
        _, start_event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert isinstance(start_event, AgentRunStartedEvent)

        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conversation_id == 1
        assert isinstance(event, AgentRunCompletedEvent)
        assert event.status == "failed"
        assert event.error == "something went wrong"

    @pytest.mark.asyncio
    async def test_execution_complete_event_interrupted_status(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_interrupt_raising_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        # Drain the AgentRunStartedEvent first
        _, start_event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert isinstance(start_event, AgentRunStartedEvent)

        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conversation_id == 1
        assert isinstance(event, AgentRunCompletedEvent)
        assert event.status == "interrupted"

    @pytest.mark.asyncio
    async def test_execution_complete_event_includes_usage_from_coro(self, manager):
        """Usage returned by the coro should appear in ExecutionCompleteEvent."""
        expected_usage = ContextUsage(
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=800,
            cache_write_tokens=200,
        )

        async def _coro_with_usage(q, ie, *, conversation_id, message_or_approvals, **kwargs) -> None:
            await _push_started(q, conversation_id)
            await _push_complete(q, conversation_id, usage=expected_usage)

        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_coro_with_usage):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        # Drain the AgentRunStartedEvent first
        _, start_event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert isinstance(start_event, AgentRunStartedEvent)

        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conversation_id == 1
        assert isinstance(event, AgentRunCompletedEvent)
        assert event.status == "completed"
        assert event.usage == expected_usage

    @pytest.mark.asyncio
    async def test_execution_complete_event_usage_none_when_coro_returns_none(self, manager):
        """usage should be None when the coro returns None (no usage data)."""
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_simple_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        # Drain the AgentRunStartedEvent first
        _, start_event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert isinstance(start_event, AgentRunStartedEvent)

        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert isinstance(event, AgentRunCompletedEvent)
        assert event.usage is None

    @pytest.mark.asyncio
    async def test_execution_complete_event_usage_none_on_interrupt(self, manager):
        """usage should be None when the coro raises AgentInterruptedError."""
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_interrupt_raising_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        # Drain the AgentRunStartedEvent first
        _, start_event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert isinstance(start_event, AgentRunStartedEvent)

        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert isinstance(event, AgentRunCompletedEvent)
        assert event.usage is None


class TestRunAgentForConversationStartOfRun:
    """Tests for start-of-run side effects in _run_agent_for_conversation."""

    @pytest.mark.asyncio
    async def test_update_last_activity_called_before_agent_run_started(self):
        """update_last_activity must be committed before AgentRunStartedEvent is broadcast.

        AgentRunStartedEvent is emitted by AgentExecutionService as its first yielded event.
        The invariant is: update_last_activity + commit happen synchronously before _drain_events
        is called, ensuring last_activity_at is persisted before the frontend refetches on startup.
        """
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, Mock, patch

        from devboard.agents.events import AgentRunCompletedEvent, AgentRunStartedEvent
        from devboard.agents.execution.manager import _run_agent_for_conversation
        from devboard.db.models import Project

        mock_services = MagicMock()
        mock_conv = MagicMock()
        mock_conv.get_parent_entity.return_value = MagicMock(spec=Project)
        mock_services.conversation_repo.get_by_id.return_value = mock_conv
        call_order: list[str] = []

        def _update_activity(c):
            call_order.append("update_last_activity")

        mock_services.conversation_repo.update_last_activity.side_effect = _update_activity

        async def tracking_stream():
            call_order.append("agent_run_started")
            yield AgentRunStartedEvent(
                conversation_id=42,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            yield AgentRunCompletedEvent(
                status="completed",
                error=None,
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        mock_exec_service = Mock()
        mock_exec_service.stream_events_for_message_or_approval.return_value = tracking_stream()

        broadcast_q: asyncio.Queue = asyncio.Queue()
        interrupt = asyncio.Event()

        with (
            patch("devboard.agents.execution.manager.DependencyResolver") as mock_dr,
            patch("devboard.agents.execution.manager.asyncio.to_thread", new=AsyncMock(return_value=None)),
            patch("devboard.agents.execution.manager.create_agent_role_for_conversation", new_callable=AsyncMock),
            patch("devboard.agents.execution.manager.create_agent_execution_service", return_value=mock_exec_service),
            patch("devboard.agents.execution.manager.ensure_project_directory", return_value="/projects/test"),
            patch("devboard.agents.execution.manager.SystemEventEmitter"),
        ):
            mock_resolver = MagicMock()
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_dr.return_value.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_dr.return_value.__aexit__ = AsyncMock(return_value=None)

            await _run_agent_for_conversation(
                broadcast_q,
                interrupt,
                conversation_id=42,
                message_or_approvals="hello",
            )

        assert mock_services.conversation_repo.update_last_activity.called

        # update_last_activity must precede the first stream event (AgentRunStartedEvent)
        assert "update_last_activity" in call_order
        assert "agent_run_started" in call_order
        assert call_order.index("update_last_activity") < call_order.index("agent_run_started")

        # AgentRunStartedEvent must be on the queue (emitted by the mock stream)
        assert not broadcast_q.empty()
        _, event = broadcast_q.get_nowait()
        assert isinstance(event, AgentRunStartedEvent)
        assert event.conversation_id == 42

    @pytest.mark.asyncio
    async def test_emit_user_event_true_puts_text_message_before_agent_run_started(self):
        """With emit_user_event=True, a user TextMessage must be pushed before AgentRunStartedEvent."""
        from unittest.mock import AsyncMock, MagicMock, Mock, patch

        from devboard.agents.execution.manager import _run_agent_for_conversation
        from devboard.db.models import Project

        mock_services = MagicMock()
        mock_conv = MagicMock()
        mock_conv.get_parent_entity.return_value = MagicMock(spec=Project)
        mock_services.conversation_repo.get_by_id.return_value = mock_conv

        async def simple_stream():
            yield AgentRunStartedEvent(
                conversation_id=42,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            yield AgentRunCompletedEvent(
                status="completed",
                error=None,
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        mock_exec_service = Mock()
        mock_exec_service.stream_events_for_message_or_approval.return_value = simple_stream()

        broadcast_q: asyncio.Queue = asyncio.Queue()
        interrupt = asyncio.Event()

        with (
            patch("devboard.agents.execution.manager.DependencyResolver") as mock_dr,
            patch("devboard.agents.execution.manager.asyncio.to_thread", new=AsyncMock(return_value=None)),
            patch("devboard.agents.execution.manager.create_agent_role_for_conversation", new_callable=AsyncMock),
            patch("devboard.agents.execution.manager.create_agent_execution_service", return_value=mock_exec_service),
            patch("devboard.agents.execution.manager.ensure_project_directory", return_value="/projects/test"),
            patch("devboard.agents.execution.manager.SystemEventEmitter"),
        ):
            mock_resolver = MagicMock()
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_dr.return_value.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_dr.return_value.__aexit__ = AsyncMock(return_value=None)

            await _run_agent_for_conversation(
                broadcast_q,
                interrupt,
                conversation_id=42,
                message_or_approvals="hello world",
                emit_user_event=True,
            )

        events = []
        while not broadcast_q.empty():
            _, event = broadcast_q.get_nowait()
            events.append(event)

        assert len(events) >= 2
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.USER
        assert events[0].text_content == "hello world"
        assert isinstance(events[1], AgentRunStartedEvent)

    @pytest.mark.asyncio
    async def test_emit_user_event_true_splits_leading_system_message_into_meta_message(self):
        """A leading <system_message> block must be emitted as a MetaMessage, not raw text.

        Workflow-action prompts (e.g. Approve & Merge) start with a wrapped git_status
        block; the live broadcast path must extract it the same way the DB/history
        replay path does, or the frontend renders the raw tag instead of a pill.
        """
        from unittest.mock import AsyncMock, MagicMock, Mock, patch

        from devboard.agents.execution.manager import _run_agent_for_conversation
        from devboard.db.models import Project

        mock_services = MagicMock()
        mock_conv = MagicMock()
        mock_conv.get_parent_entity.return_value = MagicMock(spec=Project)
        mock_services.conversation_repo.get_by_id.return_value = mock_conv

        async def simple_stream():
            yield AgentRunStartedEvent(
                conversation_id=42,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            yield AgentRunCompletedEvent(
                status="completed",
                error=None,
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        mock_exec_service = Mock()
        mock_exec_service.stream_events_for_message_or_approval.return_value = simple_stream()

        broadcast_q: asyncio.Queue = asyncio.Queue()
        interrupt = asyncio.Event()

        message = wrap_system_message("## Git Status\nNo commits yet.", "git_status") + "\n\n## Instructions\nGo."

        with (
            patch("devboard.agents.execution.manager.DependencyResolver") as mock_dr,
            patch("devboard.agents.execution.manager.asyncio.to_thread", new=AsyncMock(return_value=None)),
            patch("devboard.agents.execution.manager.create_agent_role_for_conversation", new_callable=AsyncMock),
            patch("devboard.agents.execution.manager.create_agent_execution_service", return_value=mock_exec_service),
            patch("devboard.agents.execution.manager.ensure_project_directory", return_value="/projects/test"),
            patch("devboard.agents.execution.manager.SystemEventEmitter"),
        ):
            mock_resolver = MagicMock()
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_dr.return_value.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_dr.return_value.__aexit__ = AsyncMock(return_value=None)

            await _run_agent_for_conversation(
                broadcast_q,
                interrupt,
                conversation_id=42,
                message_or_approvals=message,
                emit_user_event=True,
            )

        events = []
        while not broadcast_q.empty():
            _, event = broadcast_q.get_nowait()
            events.append(event)

        assert len(events) >= 3
        assert isinstance(events[0], MetaMessage)
        assert events[0].meta_type == MetaMessageType.GIT_STATUS
        assert "No commits yet." in events[0].text_content
        assert isinstance(events[1], TextMessage)
        assert events[1].role == MessageRole.USER
        assert "<system_message" not in events[1].text_content
        assert "## Instructions" in events[1].text_content
        assert isinstance(events[2], AgentRunStartedEvent)

    @pytest.mark.asyncio
    async def test_emit_user_event_false_does_not_emit_text_message(self):
        """With emit_user_event=False (default), no user TextMessage is emitted."""
        from unittest.mock import AsyncMock, MagicMock, Mock, patch

        from devboard.agents.execution.manager import _run_agent_for_conversation
        from devboard.db.models import Project

        mock_services = MagicMock()
        mock_conv = MagicMock()
        mock_conv.get_parent_entity.return_value = MagicMock(spec=Project)
        mock_services.conversation_repo.get_by_id.return_value = mock_conv

        async def simple_stream():
            yield AgentRunStartedEvent(
                conversation_id=42,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
            yield AgentRunCompletedEvent(
                status="completed",
                error=None,
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        mock_exec_service = Mock()
        mock_exec_service.stream_events_for_message_or_approval.return_value = simple_stream()

        broadcast_q: asyncio.Queue = asyncio.Queue()
        interrupt = asyncio.Event()

        with (
            patch("devboard.agents.execution.manager.DependencyResolver") as mock_dr,
            patch("devboard.agents.execution.manager.asyncio.to_thread", new=AsyncMock(return_value=None)),
            patch("devboard.agents.execution.manager.create_agent_role_for_conversation", new_callable=AsyncMock),
            patch("devboard.agents.execution.manager.create_agent_execution_service", return_value=mock_exec_service),
            patch("devboard.agents.execution.manager.ensure_project_directory", return_value="/projects/test"),
            patch("devboard.agents.execution.manager.SystemEventEmitter"),
        ):
            mock_resolver = MagicMock()
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_dr.return_value.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_dr.return_value.__aexit__ = AsyncMock(return_value=None)

            await _run_agent_for_conversation(
                broadcast_q,
                interrupt,
                conversation_id=42,
                message_or_approvals="hello world",
                emit_user_event=False,
            )

        events = []
        while not broadcast_q.empty():
            _, event = broadcast_q.get_nowait()
            events.append(event)

        user_text_messages = [e for e in events if isinstance(e, TextMessage) and e.role == MessageRole.USER]
        assert len(user_text_messages) == 0
        assert isinstance(events[0], AgentRunStartedEvent)


class TestInterrupt:
    """Tests for interrupt functionality."""

    @pytest.mark.asyncio
    async def test_request_interrupt_sets_event(self, manager):
        blocker = asyncio.Event()

        async def _blocking(q, ie, *, conversation_id, message_or_approvals, **kwargs):
            await blocker.wait()

        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_blocking):
            execution = manager.start_agent_execution(1, "Hello")

        result = manager.request_interrupt(1)
        assert result is True
        assert execution.interrupt_requested.is_set()

        blocker.set()
        await execution.asyncio_task

    @pytest.mark.asyncio
    async def test_request_interrupt_returns_false_when_no_active_execution(self, manager):
        result = manager.request_interrupt(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_request_interrupt_returns_false_after_completion(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_simple_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task
        await asyncio.sleep(0.01)

        result = manager.request_interrupt(1)
        assert result is False


class TestGetExecution:
    """Tests for has_active_execution and get_execution."""

    @pytest.mark.asyncio
    async def test_has_active_execution_true_when_running(self, manager):
        blocker = asyncio.Event()

        async def _blocking(q, ie, *, conversation_id, message_or_approvals, **kwargs):
            await blocker.wait()

        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_blocking):
            manager.start_agent_execution(1, "Hello")
        assert manager.has_active_execution(1) is True

        blocker.set()

    @pytest.mark.asyncio
    async def test_has_active_execution_false_when_none(self, manager):
        assert manager.has_active_execution(999) is False

    @pytest.mark.asyncio
    async def test_get_execution_returns_execution_during_run(self, manager):
        blocker = asyncio.Event()

        async def _blocking(q, ie, *, conversation_id, message_or_approvals, **kwargs):
            await blocker.wait()

        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_blocking):
            execution = manager.start_agent_execution(1, "Hello")
        fetched = manager.get_execution(1)
        assert fetched is execution

        blocker.set()

    def test_get_execution_returns_none_for_unknown(self, manager):
        assert manager.get_execution(999) is None


class TestRunSubAgentExecution:
    """Tests for ConversationExecutionManager.run_sub_agent_execution() rate-limit detection."""

    @pytest.mark.asyncio
    async def test_raises_rate_limit_error_when_both_conditions_met(self, manager):
        """Should raise SubAgentRateLimitError when model is <synthetic> and text contains 'You've hit your limit'."""
        from unittest.mock import MagicMock

        mock_conversation = MagicMock()
        mock_conversation.id = 42
        mock_role = MagicMock()
        mock_repo = MagicMock()
        mock_repo.commit = MagicMock()
        mock_config_service = MagicMock()

        # Create a text message with model="<synthetic>" and rate-limit text
        rate_limit_message = TextMessage(
            event_type="message",
            role=MessageRole.AGENT,
            text_content="You've hit your limit · resets 1:20am (Europe/London)",
            timestamp=datetime.datetime.now(datetime.UTC),
            model="<synthetic>",
        )

        mock_exec_service = MagicMock()

        async def mock_stream():
            yield rate_limit_message

        mock_exec_service.stream_events_for_message_or_approval = MagicMock(return_value=mock_stream())

        with patch("devboard.agents.execution.manager.create_agent_execution_service", return_value=mock_exec_service):
            with pytest.raises(SubAgentRateLimitError, match="Sub-agent hit rate limit"):
                await manager.run_sub_agent_execution(
                    conversation=mock_conversation,
                    role=mock_role,
                    prompt="test prompt",
                    conversation_repo=mock_repo,
                    agent_config_service=mock_config_service,
                    working_dir="/tmp",
                )

    @pytest.mark.asyncio
    async def test_no_rate_limit_error_with_synthetic_model_but_different_text(self, manager):
        """Should NOT raise SubAgentRateLimitError when model is <synthetic> but text doesn't mention limit."""
        from unittest.mock import MagicMock

        mock_conversation = MagicMock()
        mock_conversation.id = 43
        mock_role = MagicMock()
        mock_repo = MagicMock()
        mock_repo.commit = MagicMock()
        mock_config_service = MagicMock()

        # Create a text message with model="<synthetic>" but normal text
        normal_message = TextMessage(
            event_type="message",
            role=MessageRole.AGENT,
            text_content="Normal response from synthetic model",
            timestamp=datetime.datetime.now(datetime.UTC),
            model="<synthetic>",
        )

        mock_exec_service = MagicMock()

        async def mock_stream():
            yield normal_message

        mock_exec_service.stream_events_for_message_or_approval = MagicMock(return_value=mock_stream())

        with patch("devboard.agents.execution.manager.create_agent_execution_service", return_value=mock_exec_service):
            result = await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=mock_role,
                prompt="test prompt",
                conversation_repo=mock_repo,
                agent_config_service=mock_config_service,
                working_dir="/tmp",
            )
            assert result.result == "Normal response from synthetic model"
            assert result.conversation_id == 43

    @pytest.mark.asyncio
    async def test_no_rate_limit_error_with_limit_text_but_different_model(self, manager):
        """Should NOT raise SubAgentRateLimitError when text contains 'You've hit your limit' but model is different."""
        from unittest.mock import MagicMock

        mock_conversation = MagicMock()
        mock_conversation.id = 44
        mock_role = MagicMock()
        mock_repo = MagicMock()
        mock_repo.commit = MagicMock()
        mock_config_service = MagicMock()

        # Create a text message with limit text but different model
        message = TextMessage(
            event_type="message",
            role=MessageRole.AGENT,
            text_content="You've hit your limit · resets 1:20am (Europe/London)",
            timestamp=datetime.datetime.now(datetime.UTC),
            model="claude-opus",
        )

        mock_exec_service = MagicMock()

        async def mock_stream():
            yield message

        mock_exec_service.stream_events_for_message_or_approval = MagicMock(return_value=mock_stream())

        with patch("devboard.agents.execution.manager.create_agent_execution_service", return_value=mock_exec_service):
            result = await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=mock_role,
                prompt="test prompt",
                conversation_repo=mock_repo,
                agent_config_service=mock_config_service,
                working_dir="/tmp",
            )
            assert result.result == "You've hit your limit · resets 1:20am (Europe/London)"
            assert result.conversation_id == 44

    @pytest.mark.asyncio
    async def test_normal_response_returns_sub_agent_result(self, manager):
        """Should return SubAgentResult normally when neither condition is met."""
        from unittest.mock import MagicMock

        mock_conversation = MagicMock()
        mock_conversation.id = 45
        mock_role = MagicMock()
        mock_repo = MagicMock()
        mock_repo.commit = MagicMock()
        mock_config_service = MagicMock()

        # Create a normal text message
        normal_message = TextMessage(
            event_type="message",
            role=MessageRole.AGENT,
            text_content="Normal response from real model",
            timestamp=datetime.datetime.now(datetime.UTC),
            model="claude-opus",
        )

        mock_exec_service = MagicMock()

        async def mock_stream():
            yield normal_message

        mock_exec_service.stream_events_for_message_or_approval = MagicMock(return_value=mock_stream())

        with patch("devboard.agents.execution.manager.create_agent_execution_service", return_value=mock_exec_service):
            result = await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=mock_role,
                prompt="test prompt",
                conversation_repo=mock_repo,
                agent_config_service=mock_config_service,
                working_dir="/tmp",
            )
            assert result.result == "Normal response from real model"
            assert result.conversation_id == 45

    @pytest.mark.asyncio
    async def test_rate_limit_error_with_empty_stream(self, manager):
        """Should handle case where stream has no messages (no rate-limit check)."""
        from unittest.mock import MagicMock

        mock_conversation = MagicMock()
        mock_conversation.id = 46
        mock_role = MagicMock()
        mock_repo = MagicMock()
        mock_repo.commit = MagicMock()
        mock_config_service = MagicMock()

        mock_exec_service = MagicMock()

        async def mock_stream():
            yield  # Empty stream, makes this an async generator

        mock_exec_service.stream_events_for_message_or_approval = MagicMock(return_value=mock_stream())

        with patch("devboard.agents.execution.manager.create_agent_execution_service", return_value=mock_exec_service):
            result = await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=mock_role,
                prompt="test prompt",
                conversation_repo=mock_repo,
                agent_config_service=mock_config_service,
                working_dir="/tmp",
            )
            assert result.result == ""
            assert result.conversation_id == 46
