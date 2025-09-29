"""Conversation model for managing agent conversations."""

import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ParentEntityType(str, enum.Enum):
    """Enum for conversation parent entity types."""

    PROJECT = "project"
    TASK = "task"
    CODEBASE = "codebase"


if TYPE_CHECKING:
    from .messages import ConversationMessage


class Conversation(Base):
    """Model for agent conversations with polymorphic parent entity associations."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Polymorphic association to parent entity
    parent_entity_type: Mapped[ParentEntityType]
    parent_entity_id: Mapped[int]

    # For sub-conversations (internal agent-to-agent)
    parent_conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    # Relationships
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    sub_conversations: Mapped[list["Conversation"]] = relationship(back_populates="parent_conversation")
    parent_conversation: Mapped["Conversation | None"] = relationship(
        back_populates="sub_conversations", remote_side=[id]
    )

    # Unique constraint to ensure one conversation per entity (for now)
    __table_args__ = (
        UniqueConstraint(
            "parent_entity_type",
            "parent_entity_id",
            "parent_conversation_id",
            name="uq_one_conversation_per_entity",
        ),
    )
