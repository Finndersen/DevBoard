"""WebSocket router for real-time conversation event streaming."""

import asyncio

import logfire
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from devboard.agents.execution_manager import (
    ExecutionLifecycleEvent,
    ExecutionLifecycleEventType,
    ExecutionStatus,
    conversation_execution_manager,
)
from devboard.db.database import SessionLocal, engine
from devboard.db.repositories import ConversationRepository

router = APIRouter()

# How long to wait (in seconds) for new events before checking execution status
_QUEUE_GET_TIMEOUT = 1.0


def _log_pool_status(label: str, conversation_id: int) -> None:
    pool = engine.pool.status()
    logfire.info(f"WebSocket {label} for conversation {conversation_id} [db_pool: {pool}]")


@router.websocket("/{conversation_id}/ws")
async def conversation_websocket(
    conversation_id: int,
    websocket: WebSocket,
) -> None:
    """WebSocket endpoint for streaming conversation events.

    Handles exactly one execution per connection. The server closes the
    WebSocket after sending EXECUTION_COMPLETED.

    If an execution is already running when the WebSocket connects, it streams
    the remaining buffered events (reconnection support).

    Server → Client messages:
    - ConversationEvent objects (TextMessage, ToolCall, ToolResult, etc.)
    - ExecutionLifecycleEvent objects (execution_started, execution_completed)

    Client → Server: None (unidirectional). Use POST /interrupt to stop execution.
    """
    # Validate conversation with a short-lived DB session (no pool hold)
    db = SessionLocal()
    try:
        conversation_repo = ConversationRepository(db)
        conversation = conversation_repo.get_by_id(conversation_id)
        if not conversation:
            await websocket.close(code=4004, reason="Conversation not found")
            return
    finally:
        db.close()

    await websocket.accept()
    _log_pool_status("connected", conversation_id)

    try:
        await _stream_single_execution(websocket, conversation_id)
    except WebSocketDisconnect:
        _log_pool_status("client disconnected", conversation_id)
    finally:
        _log_pool_status("closing", conversation_id)


async def _stream_single_execution(websocket: WebSocket, conversation_id: int) -> None:
    """Stream events for the current execution, then close the WebSocket."""
    execution = conversation_execution_manager.get_execution(conversation_id)
    if execution is None:
        await websocket.close(code=4404, reason="No active execution")
        return

    # Notify client that we're streaming an execution
    await websocket.send_text(
        ExecutionLifecycleEvent(event=ExecutionLifecycleEventType.EXECUTION_STARTED).model_dump_json()
    )

    # Drain the event queue until sentinel or execution finishes
    while True:
        try:
            event = await asyncio.wait_for(execution.event_queue.get(), timeout=_QUEUE_GET_TIMEOUT)
        except TimeoutError:
            if execution.status != ExecutionStatus.RUNNING:
                break
            continue

        if event is None:
            break

        try:
            await websocket.send_text(event.model_dump_json())
        except WebSocketDisconnect:
            # Re-queue the event so a reconnecting WebSocket can pick it up.
            # It goes to the back of the queue, which is acceptable for a single event.
            await execution.event_queue.put(event)
            raise

    # Send completion lifecycle event
    await websocket.send_text(
        ExecutionLifecycleEvent(
            event=ExecutionLifecycleEventType.EXECUTION_COMPLETED,
            status=execution.status,
            error=execution.error,
        ).model_dump_json()
    )

    # Server closes the connection — this execution is done
    await websocket.close(code=1000, reason="Execution completed")
