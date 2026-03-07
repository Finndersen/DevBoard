"""Conversation model for managing agent conversations."""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, select
from sqlalchemy.orm import Mapped, joinedload, mapped_column, object_session, relationship

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType

from .base import Base
from .enums import EntityType

# Backwards-compatible alias
ParentEntityType = EntityType


class ParentEntityNotFoundError(ValueError):
    """Raised when a conversation's parent entity is not found in the database."""

    pass


class InvalidParentEntityTypeError(ValueError):
    """Raised when a conversation has an unrecognized parent entity type."""

    pass


if TYPE_CHECKING:
    from .codebase import Codebase
    from .messages import ConversationMessage
    from .project import Project
    from .task import Task


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
    agent_role: Mapped[AgentRoleType] = mapped_column(Enum(AgentRoleType), nullable=False)
    engine: Mapped[AgentEngine] = mapped_column(Enum(AgentEngine), nullable=False)
    model_id: Mapped[str | None] = mapped_column(
        nullable=True
    )  # e.g., "anthropic:claude-sonnet-4", or None for engine default

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
    __table_args__ = (
        Index("idx_active_conversations", "parent_entity_type", "parent_entity_id", "is_active"),
        Index("idx_conversation_external_session_id", "external_session_id"),
    )

    def get_parent_entity(self) -> "Task | Project | Codebase":
        """Get the parent entity (Task, Project, or Codebase) for this conversation.

        Note: This method performs a database query using the conversation's SQLAlchemy session.
        The method signature makes it explicit that a database operation is occurring.

        Returns:
            The parent entity instance (Task, Project, or Codebase)

        Raises:
            ParentEntityNotFoundError: If entity not found in database
            InvalidParentEntityTypeError: If parent_entity_type is not recognized
            RuntimeError: If conversation is not attached to a session
        """
        from .codebase import Codebase
        from .project import Project
        from .task import Task

        session = object_session(self)
        if session is None:
            msg = "Conversation must be attached to a session to get parent entity"
            raise RuntimeError(msg)

        if self.parent_entity_type == ParentEntityType.TASK:
            # Eager load document relationships for agent context building
            stmt = (
                select(Task)
                .options(
                    joinedload(Task.specification),
                    joinedload(Task.implementation_plan),
                    joinedload(Task.change_summary),
                )
                .where(Task.id == self.parent_entity_id)
            )
            entity = session.execute(stmt).unique().scalar_one_or_none()
        elif self.parent_entity_type == ParentEntityType.PROJECT:
            entity = session.get(Project, self.parent_entity_id)
        elif self.parent_entity_type == ParentEntityType.CODEBASE:
            entity = session.get(Codebase, self.parent_entity_id)
        else:
            msg = f"Unknown parent_entity_type: {self.parent_entity_type}"
            raise InvalidParentEntityTypeError(msg)

        if entity is None:
            msg = f"{self.parent_entity_type.value.capitalize()} with id {self.parent_entity_id} not found"
            raise ParentEntityNotFoundError(msg)

        return entity
