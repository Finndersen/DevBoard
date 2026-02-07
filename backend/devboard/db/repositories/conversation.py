"""Repository for conversation and message data access operations."""

import datetime

from pydantic_ai.messages import ModelMessage
from sqlalchemy import delete, select

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.db.models import Conversation, ConversationMessage, MessageType, ParentEntityType
from devboard.db.repositories.base import BaseRepository


class NoActiveConversationError(Exception):
    """Raised when no active conversation exists for an entity."""

    pass


class ConversationRepository(BaseRepository[Conversation]):
    """Repository handling both conversations and messages."""

    # Conversation methods
    def get_by_id(self, conversation_id: int) -> Conversation | None:
        """Get conversation by ID."""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_conversation_for_entity(
        self,
        entity_type: ParentEntityType,
        entity_id: int,
    ) -> Conversation:
        """Get the currently active conversation for an entity.

        For task lifecycle management - returns the active conversation for the
        current phase.

        Args:
            entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
            entity_id: ID of parent entity

        Returns:
            Active Conversation

        Raises:
            NoActiveConversationError: If no active conversation exists for the entity
        """
        stmt = (
            select(Conversation)
            .where(
                Conversation.parent_entity_type == entity_type,
                Conversation.parent_entity_id == entity_id,
                Conversation.is_active == True,  # noqa: E712
                Conversation.parent_conversation_id.is_(None),  # Only top-level conversations
            )
            .order_by(Conversation.created_at.desc())
        )
        conversation = self.db.execute(stmt).scalar_one_or_none()
        if not conversation:
            raise NoActiveConversationError(f"No active conversation found for {entity_type.value} with id {entity_id}")
        return conversation

    def create(
        self,
        parent_entity_type: ParentEntityType,
        parent_entity_id: int,
        agent_role: AgentRoleType,
        engine: AgentEngine,
        model_id: str | None,
        external_session_id: str | None = None,
        is_active: bool = True,
    ) -> Conversation:
        """Create a conversation with all parameters specified (low-level method).

        This is the primary low-level method for creating conversations. Higher-level
        services (like TaskService, ProjectService) should use this instead of
        constructing Conversation objects directly.

        Args:
            parent_entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
            parent_entity_id: ID of parent entity
            agent_role: Agent role for this conversation
            engine: Agent engine powering this conversation
            model_id: Model identifier (e.g., "anthropic:claude-sonnet-4") or None for default
            external_session_id: Optional external session ID for Claude Code/Gemini
            is_active: Whether this is the active conversation (default True)

        Returns:
            New Conversation instance
        """
        conversation = Conversation(
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            agent_role=agent_role,
            engine=engine,
            model_id=model_id,
            external_session_id=external_session_id,
            is_active=is_active,
        )

        self.db.add(conversation)
        self.db.flush()

        return conversation

    def update_model(self, conversation: Conversation, model_id: str | None) -> Conversation:
        """Update the model for a conversation.

        Model can be changed within the same engine (e.g., Opus → Sonnet in Claude Code).

        Args:
            conversation: Conversation instance to update
            model_id: New model identifier or None for default

        Returns:
            Updated Conversation instance
        """
        conversation.model_id = model_id
        self.db.flush()

        return conversation

    def archive_conversation(self, conversation_id: int) -> None:
        """Archive a conversation by setting is_active=False.

        Called during task phase transitions to archive the previous phase's conversation.

        Args:
            conversation_id: ID of conversation to archive
        """
        conversation = self.get_by_id(conversation_id)
        if conversation:
            conversation.is_active = False
            conversation.archived_at = datetime.datetime.now(datetime.UTC)
            self.db.flush()

    def update_external_session_id(self, conversation: Conversation, session_id: str | None) -> None:
        """Update the external session ID for a conversation.

        Used by Claude Code and other external engines to persist session continuity.

        Args:
            conversation: Conversation instance to update
            session_id: New session ID from external engine or None to clear
        """
        conversation.external_session_id = session_id
        self.db.flush()

    # Message methods (for internal agent messages)
    def get_messages(
        self,
        conversation_id: int,
        exclude_tool_calls: bool = False,
    ) -> list[ConversationMessage]:
        """Get all messages for a conversation."""
        stmt = select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
        if exclude_tool_calls:
            stmt = stmt.where(ConversationMessage.message_type.not_in([MessageType.TOOL_CALL, MessageType.TOOL_RESULT]))
        stmt = stmt.order_by(ConversationMessage.timestamp.asc())
        return list(self.db.execute(stmt).scalars().all())

    def create_message(
        self,
        conversation_id: int,
        message: ModelMessage,
    ) -> ConversationMessage:
        """Create a new message in a conversation."""
        db_message = ConversationMessage.from_pydantic_message(conversation_id, message)
        self.db.add(db_message)
        self.db.flush()
        return db_message

    def delete_messages(self, conversation_id: int) -> int:
        """Delete all messages in a conversation."""
        stmt = delete(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
        result = self.db.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined]

    def delete_tool_approval_messages(self, conversation_id: int) -> int:
        """
        Delete all messages associated with an incomplete tool approval cycle
        (including previous user message).
        """
        # Find the last user prompt message ID
        last_user_message_subq = (
            select(ConversationMessage.id)
            .where(
                ConversationMessage.message_type == MessageType.USER_PROMPT,
                ConversationMessage.conversation_id == conversation_id,
            )
            .order_by(ConversationMessage.id.desc())
            .limit(1)
            .scalar_subquery()
        )

        # Delete all messages from that point onwards
        stmt = delete(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.id >= last_user_message_subq,
        )

        return self.db.execute(stmt).rowcount  # type: ignore[attr-defined]

    def delete_by_id(self, conversation_id: int) -> bool:
        """Delete a conversation and its messages by ID.

        Args:
            conversation_id: ID of the conversation to delete

        Returns:
            True if conversation was deleted, False if not found
        """
        # Delete messages first (SQL delete bypasses cascade)
        self.delete_messages(conversation_id)

        # Delete the conversation record
        stmt = delete(Conversation).where(Conversation.id == conversation_id)
        result = self.db.execute(stmt)

        return result.rowcount > 0  # type: ignore[attr-defined]

    def delete_by_parent(self, parent_entity_type: ParentEntityType, parent_entity_id: int) -> int:
        """Hard-delete all conversations and their messages for a parent entity.

        Used during parent entity deletion to ensure no orphaned conversation records.
        Messages are explicitly deleted first because we use SQL delete() which bypasses
        ORM cascade rules. Using ORM delete would be slower for bulk operations.

        Args:
            parent_entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
            parent_entity_id: ID of parent entity

        Returns:
            Number of conversations deleted
        """
        # Get all conversation IDs for the parent
        stmt = select(Conversation.id).where(
            Conversation.parent_entity_type == parent_entity_type,
            Conversation.parent_entity_id == parent_entity_id,
        )
        conversation_ids = list(self.db.execute(stmt).scalars().all())

        if not conversation_ids:
            return 0

        # Delete all messages for these conversations first
        msg_stmt = delete(ConversationMessage).where(ConversationMessage.conversation_id.in_(conversation_ids))
        self.db.execute(msg_stmt)

        # Delete the conversations
        conv_stmt = delete(Conversation).where(Conversation.id.in_(conversation_ids))
        result = self.db.execute(conv_stmt)

        return result.rowcount  # type: ignore[attr-defined]
