"""WebSocket router for real-time conversation event streaming."""

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

    try:
        while True:
            conversation_id, event = await manager.broadcast_queue.get()
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
