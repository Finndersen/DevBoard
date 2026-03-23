"""Types and data structures for agent execution tracking."""

import asyncio
import dataclasses
import datetime
from enum import StrEnum


class ExecutionStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


@dataclasses.dataclass
class ConversationExecution:
    """Tracks a single active agent execution for a conversation."""

    conversation_id: int
    interrupt_requested: asyncio.Event
    asyncio_task: asyncio.Task[None]
    status: ExecutionStatus
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    error: str | None = None
