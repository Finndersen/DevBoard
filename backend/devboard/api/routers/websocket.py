"""WebSocket router for real-time conversation event streaming."""

import asyncio
import time

import logfire
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from devboard.agents.execution.registry import get_execution_manager

router = APIRouter()


@router.websocket("/ws")
async def multiplexed_websocket(websocket: WebSocket) -> None:
    """Multiplexed WebSocket endpoint for streaming conversation events.

    A single persistent connection that receives events for all active executions.
    Each message includes a conversation_id field to identify which conversation
    the event belongs to.

    Server → Client: ConversationEvent objects tagged with conversation_id
    Client → Server: None (unidirectional). Use POST /interrupt to stop execution.
    """
    await websocket.accept()
    manager = get_execution_manager()

    # Receives the disconnect frame (or any client message). Races against
    # broadcast_queue.get() so we exit cleanly when the client disconnects
    # even when the queue is empty and no events are being published.
    receive_task = asyncio.create_task(websocket.receive())
    try:
        while True:
            get_task = asyncio.create_task(manager.broadcast_queue.get())
            done, _ = await asyncio.wait(
                {get_task, receive_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if receive_task in done:
                # Client disconnected or sent an unexpected message — exit.
                get_task.cancel()
                try:
                    # If get_task completed (item already dequeued), put it back.
                    manager.broadcast_queue.put_nowait(await get_task)
                except (asyncio.CancelledError, asyncio.QueueFull):
                    pass
                return

            conversation_id, event = get_task.result()
            t0 = time.monotonic()
            event_data = event.model_dump(mode="json")
            dump_ms = (time.monotonic() - t0) * 1000
            if dump_ms > 20:
                logfire.warn(
                    "Slow model_dump in WS handler",
                    event_type=event.event_type,
                    conversation_id=conversation_id,
                    dump_ms=f"{dump_ms:.1f}",
                )
            event_data["conversation_id"] = conversation_id
            await websocket.send_json(event_data)
    except WebSocketDisconnect:
        pass
    finally:
        receive_task.cancel()
        try:
            await receive_task
        except (asyncio.CancelledError, Exception):
            pass
