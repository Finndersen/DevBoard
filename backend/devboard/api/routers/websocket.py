"""WebSocket router for real-time conversation event streaming."""

import asyncio

import logfire
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from devboard.agents.execution_manager import (
    ExecutionLifecycleEvent,
    ExecutionLifecycleEventType,
    ExecutionStatus,
    conversation_execution_manager,
)
from devboard.db.database import get_db
from devboard.db.repositories import ConversationRepository

router = APIRouter()

# How long to wait (in seconds) for new events before checking execution status
_QUEUE_GET_TIMEOUT = 1.0
# How long to wait (in seconds) between polls for a new execution
_EXECUTION_POLL_INTERVAL = 0.5


@router.websocket("/{conversation_id}/ws")
async def conversation_websocket(
    conversation_id: int,
    websocket: WebSocket,
    db: Session = Depends(get_db),
) -> None:
    """WebSocket endpoint for streaming conversation events.

    Connects to the event queue for the given conversation. Events are sent
    as JSON as they are pushed by the background execution task.

    Server → Client messages:
    - ConversationEvent objects (TextMessage, ToolCall, ToolResult, etc.)
    - ExecutionLifecycleEvent objects (execution_started, execution_completed)

    Client → Server: None (unidirectional). Use POST /interrupt to stop execution.

    Connection lifecycle:
    - Can be opened before, during, or after an execution
    - Remains open across multiple sequential executions
    - Client disconnection does not affect background execution
    """
    conversation_repo = ConversationRepository(db)
    conversation = conversation_repo.get_by_id(conversation_id)
    if not conversation:
        await websocket.close(code=4004, reason="Conversation not found")
        return

    await websocket.accept()
    logfire.info(f"WebSocket connected for conversation {conversation_id}")

    try:
        await _stream_executions(websocket, conversation_id)
    except WebSocketDisconnect:
        logfire.info(f"WebSocket disconnected for conversation {conversation_id}")


async def _stream_executions(websocket: WebSocket, conversation_id: int) -> None:
    """Loop indefinitely: wait for executions, stream events, repeat."""
    last_seen_started_at = None

    while True:
        # Poll until a new execution appears
        while True:
            execution = conversation_execution_manager.get_execution(conversation_id)
            if execution is not None and execution.started_at != last_seen_started_at:
                break
            await asyncio.sleep(_EXECUTION_POLL_INTERVAL)

        last_seen_started_at = execution.started_at

        # Notify client that an execution is being consumed
        await websocket.send_text(
            ExecutionLifecycleEvent(event=ExecutionLifecycleEventType.EXECUTION_STARTED).model_dump_json()
        )

        # Drain the event queue until sentinel or timeout with completed status
        while True:
            try:
                event = await asyncio.wait_for(execution.event_queue.get(), timeout=_QUEUE_GET_TIMEOUT)
            except TimeoutError:
                # No new events — check if execution finished without us consuming sentinel
                # (possible if a previous WS connection already consumed it)
                if execution.status != ExecutionStatus.RUNNING:
                    break
                continue

            if event is None:
                # Sentinel — execution completed normally
                break

            await websocket.send_text(event.model_dump_json())

        # Send completion lifecycle event
        await websocket.send_text(
            ExecutionLifecycleEvent(
                event=ExecutionLifecycleEventType.EXECUTION_COMPLETED,
                status=execution.status,
                error=execution.error,
            ).model_dump_json()
        )
