"""BackgroundAgentRun database model."""

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class BackgroundAgentRunStatus(StrEnum):
    """Statuses for a background agent run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


if TYPE_CHECKING:
    from .background_agent import BackgroundAgent
    from .conversation import Conversation


class BackgroundAgentRun(Base):
    """Record of a single execution of a background agent."""

    __tablename__ = "background_agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("background_agents.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)

    triggered_by: Mapped[str] = mapped_column(String(255))
    trigger_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    status: Mapped[BackgroundAgentRunStatus] = mapped_column(Enum(BackgroundAgentRunStatus))

    state_before: Mapped[dict[str, Any]] = mapped_column(JSON)
    state_after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent: Mapped["BackgroundAgent"] = relationship(back_populates="runs")
    conversation: Mapped["Conversation"] = relationship()
