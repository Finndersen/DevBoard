"""Tests for ConversationExecutionManager."""

import asyncio
import datetime
from unittest.mock import patch

import pytest

from devboard.agents.events import ExecutionCompleteEvent, MessageRole, TextMessage
from devboard.agents.exceptions import AgentInterruptedError, ConversationBusyError
from devboard.agents.execution.manager import ConversationExecutionManager
from devboard.agents.execution.types import ConversationExecution, ExecutionStatus


@pytest.fixture
def manager() -> ConversationExecutionManager:
    """Return a fresh ConversationExecutionManager for each test."""
    return ConversationExecutionManager()


async def _simple_coro(q, ie, *, conversation_id, message_or_approvals) -> None:
    pass


async def _interrupt_raising_coro(q, ie, *, conversation_id, message_or_approvals) -> None:
    raise AgentInterruptedError("interrupted")


async def _error_raising_coro(q, ie, *, conversation_id, message_or_approvals) -> None:
    raise ValueError("something went wrong")


async def _event_pushing_coro(q, ie, *, conversation_id, message_or_approvals) -> None:
    event = TextMessage(
        event_type="message",
        role=MessageRole.AGENT,
        text_content="hello",
        timestamp=datetime.datetime.now(datetime.UTC),
    )
    await q.put((conversation_id, event))


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

        async def _blocking(q, ie, *, conversation_id, message_or_approvals):
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
    async def test_execution_complete_event_pushed_on_completion(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_simple_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conversation_id == 1
        assert isinstance(event, ExecutionCompleteEvent)
        assert event.status == "completed"
        assert event.error is None

    @pytest.mark.asyncio
    async def test_events_then_execution_complete_in_broadcast_queue(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_event_pushing_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        conv_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conv_id == 1
        assert isinstance(event, TextMessage)

        conv_id, complete_event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conv_id == 1
        assert isinstance(complete_event, ExecutionCompleteEvent)

    @pytest.mark.asyncio
    async def test_execution_complete_event_includes_error_on_failure(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_error_raising_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conversation_id == 1
        assert isinstance(event, ExecutionCompleteEvent)
        assert event.status == "failed"
        assert event.error == "something went wrong"

    @pytest.mark.asyncio
    async def test_execution_complete_event_interrupted_status(self, manager):
        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_interrupt_raising_coro):
            execution = manager.start_agent_execution(1, "Hello")
        await execution.asyncio_task

        conversation_id, event = await asyncio.wait_for(manager.broadcast_queue.get(), timeout=1.0)
        assert conversation_id == 1
        assert isinstance(event, ExecutionCompleteEvent)
        assert event.status == "interrupted"


class TestInterrupt:
    """Tests for interrupt functionality."""

    @pytest.mark.asyncio
    async def test_request_interrupt_sets_event(self, manager):
        blocker = asyncio.Event()

        async def _blocking(q, ie, *, conversation_id, message_or_approvals):
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

        async def _blocking(q, ie, *, conversation_id, message_or_approvals):
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

        async def _blocking(q, ie, *, conversation_id, message_or_approvals):
            await blocker.wait()

        with patch("devboard.agents.execution.manager._run_agent_for_conversation", new=_blocking):
            execution = manager.start_agent_execution(1, "Hello")
        fetched = manager.get_execution(1)
        assert fetched is execution

        blocker.set()

    def test_get_execution_returns_none_for_unknown(self, manager):
        assert manager.get_execution(999) is None
