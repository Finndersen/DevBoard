"""Background agent database models."""

import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import JSON, Column, Enum, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from devboard.agents.engines import AgentEngine

from .base import Base
from .enums import EntityType

if TYPE_CHECKING:
    from .background_agent_run import BackgroundAgentRun
    from .mcp_server import MCPTool


# Junction table for many-to-many relationship between BackgroundAgent and MCPTool
background_agent_mcp_tools = Table(
    "background_agent_mcp_tools",
    Base.metadata,
    Column("agent_id", Integer, ForeignKey("background_agents.id", ondelete="CASCADE"), primary_key=True),
    Column("mcp_tool_id", Integer, ForeignKey("mcp_tools.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("agent_id", "mcp_tool_id", name="uq_background_agent_mcp_tool"),
)


class BackgroundAgent(Base):
    """User-defined autonomous background agent configuration."""

    __tablename__ = "background_agents"
    entity_type: ClassVar[EntityType] = EntityType.BACKGROUND_AGENT

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt: Mapped[str] = mapped_column(Text)
    engine: Mapped[AgentEngine] = mapped_column(Enum(AgentEngine))
    model_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    # Many-to-many relationship to MCPTool
    enabled_mcp_tools: Mapped[list["MCPTool"]] = relationship(
        "MCPTool",
        secondary=background_agent_mcp_tools,
        lazy="selectin",
    )

    event_triggers: Mapped[list["BackgroundAgentEventTrigger"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    schedule_triggers: Mapped[list["BackgroundAgentScheduleTrigger"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    runs: Mapped[list["BackgroundAgentRun"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )


class BackgroundAgentEventTrigger(Base):
    """Event-based trigger for a background agent."""

    __tablename__ = "background_agent_event_triggers"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("background_agents.id", ondelete="CASCADE"), index=True)
    event_type_pattern: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    agent: Mapped["BackgroundAgent"] = relationship(back_populates="event_triggers")


class BackgroundAgentScheduleTrigger(Base):
    """Schedule-based trigger for a background agent."""

    __tablename__ = "background_agent_schedule_triggers"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("background_agents.id", ondelete="CASCADE"), index=True)
    cron_expression: Mapped[str] = mapped_column(String(255))
    last_triggered_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    agent: Mapped["BackgroundAgent"] = relationship(back_populates="schedule_triggers")
