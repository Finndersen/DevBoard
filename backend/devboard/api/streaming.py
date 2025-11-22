"""Streaming response utilities for API endpoints."""

import json
from collections.abc import AsyncIterator, Callable

import logfire
from fastapi.responses import StreamingResponse

from devboard.agents.events import ConversationEvent


def stream_conversation_events(
    event_stream: AsyncIterator[ConversationEvent],
    exception_handler: Callable[[Exception], None] | None = None,
) -> StreamingResponse:
    """Create a StreamingResponse that streams ConversationEvents as NDJSON.

    Args:
        event_stream: AsyncIterator yielding ConversationEvent objects
        exception_handler: Optional callback to handle exceptions raised during event iteration.
            Should raise an appropriate HTTPException. If None, exceptions propagate naturally.

    Returns:
        StreamingResponse with NDJSON formatted events (newline-delimited JSON)
    """

    async def event_generator():
        try:
            async for event in event_stream:
                logfire.info(f"Streaming conversation event: {repr(event)}")
                yield json.dumps(event.model_dump(mode="json")) + "\n"
        except Exception as e:
            if exception_handler:
                exception_handler(e)
            else:
                raise

    return StreamingResponse(event_generator(), media_type="text/plain")
