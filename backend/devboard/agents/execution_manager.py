"""Conversation execution manager for background task execution."""

import asyncio
import dataclasses
import datetime
from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import Any, Literal

import logfire
from opentelemetry import context as otel_context
from pydantic import BaseModel

from devboard.agents.events import ConversationEvent
from devboard.agents.exceptions import AgentInterruptedError, ConversationBusyError


class ExecutionStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class ExecutionLifecycleEventType(StrEnum):
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"


class ExecutionLifecycleEvent(BaseModel):
    """WebSocket lifecycle message for execution state changes."""

    event_type: Literal["execution_lifecycle"] = "execution_lifecycle"
    event: ExecutionLifecycleEventType
    status: ExecutionStatus | None = None
    error: str | None = None


# Grace period (seconds) to allow WebSocket reconnection after execution completes.
# After this window, the execution record is removed; all data is available via message history.
EXECUTION_CLEANUP_GRACE_PERIOD_SECONDS = 60

# Type alias for a coroutine factory that accepts (event_queue, interrupt_event)
ExecutionCoroutineFactory = Callable[
    [asyncio.Queue[ConversationEvent | None], asyncio.Event],
    Coroutine[Any, Any, None],
]


@dataclasses.dataclass
class ConversationExecution:
    """Tracks a single active agent execution for a conversation."""

    conversation_id: int
    event_queue: asyncio.Queue[ConversationEvent | None]
    interrupt_requested: asyncio.Event
    asyncio_task: asyncio.Task[None]
    status: ExecutionStatus
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error: str | None = None
    cleanup_task: asyncio.Task[None] | None = None


class ConversationExecutionManager:
    """Process-level singleton that tracks all active agent executions.

    Manages background task lifecycle, event queues, and interrupt signaling.
    Keyed by conversation_id — at most one execution per conversation at a time.
    """

    def __init__(self) -> None:
        self._executions: dict[int, ConversationExecution] = {}

    def start_execution(
        self,
        conversation_id: int,
        coro_factory: ExecutionCoroutineFactory,
    ) -> ConversationExecution:
        """Start a background execution for a conversation.

        Args:
            conversation_id: The conversation to run the execution for
            coro_factory: Callable that accepts (event_queue, interrupt_event) and returns a coroutine.
                          Called immediately to create the background task.

        Returns:
            The created ConversationExecution

        Raises:
            ConversationBusyError: If an active execution already exists for this conversation
        """
        existing = self._executions.get(conversation_id)
        if existing and existing.status == ExecutionStatus.RUNNING:
            raise ConversationBusyError(conversation_id)
        # Cancel any pending cleanup from a previous execution so it cannot
        # delete the new execution after the grace period expires.
        if existing and existing.cleanup_task and not existing.cleanup_task.done():
            existing.cleanup_task.cancel()

        event_queue: asyncio.Queue[ConversationEvent | None] = asyncio.Queue()
        interrupt_event = asyncio.Event()

        coro = coro_factory(event_queue, interrupt_event)
        task = asyncio.create_task(self._run_wrapper(conversation_id, coro, event_queue))

        execution = ConversationExecution(
            conversation_id=conversation_id,
            event_queue=event_queue,
            interrupt_requested=interrupt_event,
            asyncio_task=task,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.datetime.now(datetime.UTC),
        )
        self._executions[conversation_id] = execution
        logfire.info(f"Started execution for conversation {conversation_id}")
        return execution

    async def _run_wrapper(
        self,
        conversation_id: int,
        coro: Coroutine[Any, Any, None],
        event_queue: asyncio.Queue[ConversationEvent | None],
    ) -> None:
        """Run the coroutine and handle lifecycle transitions."""
        execution = self._executions.get(conversation_id)
        if not execution:
            return

        # Detach from the request's trace context — background tasks run outside
        # the request lifecycle and should produce their own root span in Logfire.
        token = otel_context.attach(otel_context.Context())
        try:
            with logfire.span("background.agent_execution", conversation_id=conversation_id):
                try:
                    await coro
                    execution.status = ExecutionStatus.COMPLETED
                    logfire.info(f"Execution completed for conversation {conversation_id}")
                except AgentInterruptedError:
                    execution.status = ExecutionStatus.INTERRUPTED
                    logfire.info(f"Execution interrupted for conversation {conversation_id}")
                except Exception as e:
                    execution.status = ExecutionStatus.FAILED
                    execution.error = str(e)
                    logfire.exception(f"Execution failed for conversation {conversation_id}: {e}")
                finally:
                    execution.completed_at = datetime.datetime.now(datetime.UTC)
                    # Push sentinel to signal completion to WebSocket consumers
                    await event_queue.put(None)
                    # Schedule cleanup after grace period, keyed by started_at to avoid
                    # deleting a newer execution if one is started before this cleanup runs.
                    execution.cleanup_task = asyncio.create_task(
                        self._schedule_cleanup(conversation_id, execution.started_at)
                    )
        finally:
            otel_context.detach(token)

    async def _schedule_cleanup(self, conversation_id: int, started_at: datetime.datetime) -> None:
        """Remove execution record after a grace period for reconnection.

        Only removes the execution if it still matches started_at, preventing accidental
        deletion of a newer execution started after this one completed.
        """
        await asyncio.sleep(EXECUTION_CLEANUP_GRACE_PERIOD_SECONDS)
        execution = self._executions.get(conversation_id)
        if execution and execution.started_at == started_at:
            self._executions.pop(conversation_id, None)
            logfire.debug(f"Cleaned up execution record for conversation {conversation_id}")

    def get_execution(self, conversation_id: int) -> ConversationExecution | None:
        return self._executions.get(conversation_id)

    def has_active_execution(self, conversation_id: int) -> bool:
        execution = self._executions.get(conversation_id)
        return execution is not None and execution.status == ExecutionStatus.RUNNING

    def list_active_executions(self) -> list[ConversationExecution]:
        """Return all currently running executions."""
        return [e for e in self._executions.values() if e.status == ExecutionStatus.RUNNING]

    def request_interrupt(self, conversation_id: int) -> bool:
        """Request interrupt for the active execution.

        Returns:
            True if an active execution was found and signaled, False otherwise.
        """
        execution = self._executions.get(conversation_id)
        if execution and execution.status == ExecutionStatus.RUNNING:
            execution.interrupt_requested.set()
            logfire.info(f"Interrupt requested for conversation {conversation_id}")
            return True
        return False


# Process-level singleton
conversation_execution_manager = ConversationExecutionManager()
