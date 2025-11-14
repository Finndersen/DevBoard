"""Streaming response utilities for API endpoints."""

import json
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from devboard.agents.events import ConversationEvent


def stream_conversation_events(events: AsyncIterator[ConversationEvent]) -> StreamingResponse:
    """Create a StreamingResponse that streams ConversationEvents as NDJSON.

    Args:
        events: AsyncIterator yielding ConversationEvent objects

    Returns:
        StreamingResponse with NDJSON formatted events (newline-delimited JSON)
    """

    async def event_generator():
        async for event in events:
            yield json.dumps(event.model_dump(mode="json")) + "\n"

    return StreamingResponse(event_generator(), media_type="text/plain")
