"""Conversation model for managing agent conversations."""

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.roles.types import AgentRole

from .base import Base


class ParentEntityType(StrEnum):
    """Enum for conversation parent entity types."""

    PROJECT = "project"
    TASK = "task"
    CODEBASE = "codebase"


if TYPE_CHECKING:
    from .messages import ConversationMessage


class Conversation(Base):
    """Model for agent conversations with polymorphic parent entity associations.

    Supports multiple agent engines (INTERNAL, Claude Code, Gemini CLI) and
    phase-based conversation management for tasks.

    Each conversation snapshots its agent configuration at creation time:
    - agent_role: Generally immutable, but can be updated when transitioning task phases with same engine
    - engine: Immutable (INTERNAL, CLAUDE_CODE, GEMINI_CLI)
    - model_id: Mutable (can be changed within same engine)

    Attributes:
        id: Primary key
        parent_entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
        parent_entity_id: ID of parent entity
        parent_conversation_id: For nested sub-conversations (internal agent-to-agent)
        agent_role: Agent role for this conversation (AgentRole enum value)
        engine: Agent engine powering this conversation
        model_id: Model identifier (e.g., "anthropic:claude-sonnet-4")
        external_session_id: Session ID for external engines (Claude Code, Gemini)
        is_active: Whether this is the current active conversation for the entity
        archived_at: When conversation was archived (phase transition)
        created_at: When conversation was created
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Polymorphic association to parent entity
    parent_entity_type: Mapped[ParentEntityType]
    parent_entity_id: Mapped[int]

    # For sub-conversations (internal agent-to-agent)
    parent_conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)

    # Agent configuration snapshot (immutable after creation, except model_id)
    agent_role: Mapped[AgentRole] = mapped_column(Enum(AgentRole), nullable=False)
    engine: Mapped[AgentEngine] = mapped_column(Enum(AgentEngine), nullable=False)
    model_id: Mapped[str] = mapped_column(nullable=False)  # e.g., "anthropic:claude-sonnet-4"

    # External session management
    external_session_id: Mapped[str | None] = mapped_column(nullable=True)

    # Phase-based conversation management
    is_active: Mapped[bool] = mapped_column(default=True)
    archived_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationships
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    sub_conversations: Mapped[list["Conversation"]] = relationship(back_populates="parent_conversation")
    parent_conversation: Mapped["Conversation | None"] = relationship(
        back_populates="sub_conversations", remote_side=[id]
    )

    # Index for efficiently querying active conversations
    __table_args__ = (Index("idx_active_conversations", "parent_entity_type", "parent_entity_id", "is_active"),)
