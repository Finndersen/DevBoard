"""Tests for ConversationExecutionManager."""

import asyncio
import datetime

import pytest

from devboard.agents.exceptions import AgentInterruptedError, ConversationBusyError
from devboard.agents.execution_manager import (
    ConversationExecution,
    ConversationExecutionManager,
    ExecutionStatus,
)


@pytest.fixture
def manager() -> ConversationExecutionManager:
    """Return a fresh ConversationExecutionManager for each test."""
    return ConversationExecutionManager()


async def _simple_coro(
    event_queue: asyncio.Queue,
    interrupt_event: asyncio.Event,
) -> None:
    """Simple coroutine that completes immediately."""


async def _interrupt_raising_coro(
    event_queue: asyncio.Queue,
    interrupt_event: asyncio.Event,
) -> None:
    """Coroutine that raises AgentInterruptedError."""
    raise AgentInterruptedError("interrupted")


async def _error_raising_coro(
    event_queue: asyncio.Queue,
    interrupt_event: asyncio.Event,
) -> None:
    """Coroutine that raises a generic exception."""
    raise ValueError("something went wrong")


async def _event_pushing_coro(
    event_queue: asyncio.Queue,
    interrupt_event: asyncio.Event,
) -> None:
    """Coroutine that pushes events before completing."""
    import datetime

    from devboard.agents.events import MessageRole, TextMessage

    event = TextMessage(
        event_type="message",
        role=MessageRole.AGENT,
        text_content="hello",
        timestamp=datetime.datetime.now(datetime.UTC),
    )
    await event_queue.put(event)


class TestStartExecution:
    """Tests for ConversationExecutionManager.start_execution()."""

    @pytest.mark.asyncio
    async def test_start_execution_creates_running_execution(self, manager):
        """Starting an execution should create a RUNNING ConversationExecution."""
        execution = manager.start_execution(1, _simple_coro)

        assert isinstance(execution, ConversationExecution)
        assert execution.conversation_id == 1
        assert execution.status == ExecutionStatus.RUNNING
        assert not execution.interrupt_requested.is_set()
        assert isinstance(execution.started_at, datetime.datetime)
        assert execution.completed_at is None

        # Wait for completion
        await execution.asyncio_task

    @pytest.mark.asyncio
    async def test_start_execution_raises_conflict_if_already_running(self, manager):
        """Should raise ConversationBusyError if an execution is already active."""
        blocker = asyncio.Event()

        async def _blocking_coro(q, ie):
            await blocker.wait()

        manager.start_execution(1, _blocking_coro)

        with pytest.raises(ConversationBusyError):
            manager.start_execution(1, _simple_coro)

        blocker.set()

    @pytest.mark.asyncio
    async def test_start_execution_allows_new_after_completion(self, manager):
        """Should allow a new execution after the previous one completes."""
        first = manager.start_execution(1, _simple_coro)
        await first.asyncio_task
        # Give cleanup a chance to mark as completed
        await asyncio.sleep(0.01)

        second = manager.start_execution(1, _simple_coro)
        assert second is not first
        await second.asyncio_task


class TestExecutionLifecycle:
    """Tests for execution status transitions."""

    @pytest.mark.asyncio
    async def test_completed_status_on_success(self, manager):
        """Successful coroutine should result in COMPLETED status."""
        execution = manager.start_execution(1, _simple_coro)
        await execution.asyncio_task
        await asyncio.sleep(0.01)

        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_interrupted_status_on_agent_interrupted_error(self, manager):
        """AgentInterruptedError should result in INTERRUPTED status."""
        execution = manager.start_execution(1, _interrupt_raising_coro)
        await execution.asyncio_task
        await asyncio.sleep(0.01)

        assert execution.status == ExecutionStatus.INTERRUPTED
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_failed_status_on_generic_exception(self, manager):
        """Generic exception should result in FAILED status with error message."""
        execution = manager.start_execution(1, _error_raising_coro)
        await execution.asyncio_task
        await asyncio.sleep(0.01)

        assert execution.status == ExecutionStatus.FAILED
        assert execution.error == "something went wrong"
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_sentinel_pushed_to_queue_on_completion(self, manager):
        """None sentinel should be pushed to the event queue after execution."""
        execution = manager.start_execution(1, _simple_coro)
        await execution.asyncio_task

        sentinel = await asyncio.wait_for(execution.event_queue.get(), timeout=1.0)
        assert sentinel is None

    @pytest.mark.asyncio
    async def test_events_then_sentinel_in_queue(self, manager):
        """Events should be in the queue before the sentinel."""
        execution = manager.start_execution(1, _event_pushing_coro)
        await execution.asyncio_task

        event = await asyncio.wait_for(execution.event_queue.get(), timeout=1.0)
        assert event is not None  # The text message event
        sentinel = await asyncio.wait_for(execution.event_queue.get(), timeout=1.0)
        assert sentinel is None


class TestInterrupt:
    """Tests for interrupt functionality."""

    @pytest.mark.asyncio
    async def test_request_interrupt_sets_event(self, manager):
        """request_interrupt should set the interrupt_requested event."""
        blocker = asyncio.Event()

        async def _blocking_coro(q, ie):
            await blocker.wait()

        execution = manager.start_execution(1, _blocking_coro)

        result = manager.request_interrupt(1)
        assert result is True
        assert execution.interrupt_requested.is_set()

        blocker.set()
        await execution.asyncio_task

    @pytest.mark.asyncio
    async def test_request_interrupt_returns_false_when_no_active_execution(self, manager):
        """request_interrupt should return False when no execution is active."""
        result = manager.request_interrupt(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_request_interrupt_returns_false_after_completion(self, manager):
        """request_interrupt should return False after execution completes."""
        execution = manager.start_execution(1, _simple_coro)
        await execution.asyncio_task
        await asyncio.sleep(0.01)

        result = manager.request_interrupt(1)
        assert result is False


class TestGetExecution:
    """Tests for has_active_execution and get_execution."""

    @pytest.mark.asyncio
    async def test_has_active_execution_true_when_running(self, manager):
        """has_active_execution should return True for a running execution."""
        blocker = asyncio.Event()

        async def _blocking_coro(q, ie):
            await blocker.wait()

        manager.start_execution(1, _blocking_coro)
        assert manager.has_active_execution(1) is True

        blocker.set()

    @pytest.mark.asyncio
    async def test_has_active_execution_false_when_none(self, manager):
        """has_active_execution should return False when no execution exists."""
        assert manager.has_active_execution(999) is False

    @pytest.mark.asyncio
    async def test_get_execution_returns_execution_during_run(self, manager):
        """get_execution should return the execution object while running."""
        blocker = asyncio.Event()

        async def _blocking_coro(q, ie):
            await blocker.wait()

        execution = manager.start_execution(1, _blocking_coro)
        fetched = manager.get_execution(1)
        assert fetched is execution

        blocker.set()

    def test_get_execution_returns_none_for_unknown(self, manager):
        """get_execution should return None for unknown conversation."""
        assert manager.get_execution(999) is None
