"""Streaming response utilities for API endpoints."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import logfire
from fastapi import Request
from fastapi.responses import StreamingResponse

from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType, describe_event


@asynccontextmanager
async def cancel_on_disconnect(request: Request):
    """Context manager that cancels the current task when client disconnects.

    Spawns a background task that monitors the request for HTTP disconnect messages.
    When disconnect is detected, cancels the task that entered this context.

    Args:
        request: FastAPI Request object to monitor for disconnection
    """
    task_to_cancel = asyncio.current_task()
    disconnect_task: asyncio.Task | None = None

    async def monitor_disconnect():
        try:
            while True:
                message = await request.receive()
                if message["type"] == "http.disconnect":
                    logfire.info("Client disconnected, cancelling agent task")
                    if task_to_cancel:
                        task_to_cancel.cancel()
                    return
        except asyncio.CancelledError:
            pass

    try:
        disconnect_task = asyncio.create_task(monitor_disconnect())
        yield
    finally:
        if disconnect_task and not disconnect_task.done():
            disconnect_task.cancel()
            try:
                await disconnect_task
            except asyncio.CancelledError:
                pass


def stream_conversation_events(
    event_stream: AsyncIterator[ConversationEvent],
    request: Request,
    exception_handler: Callable[[Exception], None] | None = None,
) -> StreamingResponse:
    """Create a StreamingResponse that streams ConversationEvents as NDJSON.

    Args:
        event_stream: AsyncIterator yielding ConversationEvent objects
        request: FastAPI Request for disconnect detection and cancellation
        exception_handler: Optional callback to handle exceptions raised during event iteration.
            Should raise an appropriate HTTPException. If None, exceptions propagate naturally.

    Returns:
        StreamingResponse with NDJSON formatted events (newline-delimited JSON)
    """

    async def event_generator():
        try:
            async with cancel_on_disconnect(request):
                async for event in event_stream:
                    logfire.info("Streaming conversation event: {event_desc}", event_desc=describe_event(event))
                    yield json.dumps(event.model_dump(mode="json")) + "\n"
        except asyncio.CancelledError:
            logfire.info("Stream cancelled due to client disconnect")
            interrupted_event = SystemEvent(
                type=SystemEventType.STREAM_INTERRUPTED,
                data={"message": "Stream interrupted by client"},
                timestamp=datetime.now(UTC),
            )
            yield json.dumps(interrupted_event.model_dump(mode="json")) + "\n"
        except Exception as e:
            if exception_handler:
                exception_handler(e)
            else:
                raise
        finally:
            if hasattr(event_stream, "aclose"):
                await event_stream.aclose()

    return StreamingResponse(event_generator(), media_type="text/plain")
