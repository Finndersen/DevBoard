"""Types and data structures for agent execution tracking."""

import asyncio
import dataclasses
import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from devboard.agents.events import ConversationEvent


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
