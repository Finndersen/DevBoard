"""Repository for conversation and message data access operations."""

import datetime

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from sqlalchemy import delete, select

from devboard.agents.agent_engines import AgentEngine
from devboard.agents.types import AgentRole
from devboard.db.models import Conversation, ConversationMessage, MessageType, ParentEntityType
from devboard.db.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    """Repository handling both conversations and messages."""

    # Conversation methods
    def get_or_create_for_entity(
        self,
        entity_type: ParentEntityType,
        entity_id: int,
        parent_conversation_id: int | None = None,
    ) -> Conversation:
        """Get existing or create new conversation for entity."""
        stmt = select(Conversation).where(
            Conversation.parent_entity_type == entity_type,
            Conversation.parent_entity_id == entity_id,
        )

        # Handle both main conversations and sub-conversations
        if parent_conversation_id is None:
            stmt = stmt.where(Conversation.parent_conversation_id.is_(None))
        else:
            stmt = stmt.where(Conversation.parent_conversation_id == parent_conversation_id)

        conversation = self.db.execute(stmt).scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                parent_entity_type=entity_type,
                parent_entity_id=entity_id,
                parent_conversation_id=parent_conversation_id,
            )
            self.db.add(conversation)
            self.db.flush()

        return conversation

    def get_by_id(self, conversation_id: int) -> Conversation | None:
        """Get conversation by ID."""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_conversation_for_entity(
        self,
        entity_type: ParentEntityType,
        entity_id: int,
    ) -> Conversation | None:
        """Get the currently active conversation for an entity.

        For task lifecycle management - returns the active conversation for the
        current phase. Returns None if no active conversation exists.

        Args:
            entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
            entity_id: ID of parent entity

        Returns:
            Active Conversation or None
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
        return self.db.execute(stmt).scalar_one_or_none()

    def create(
        self,
        parent_entity_type: ParentEntityType,
        parent_entity_id: int,
        agent_role: AgentRole,
        engine: AgentEngine,
        model_id: str,
        external_session_id: str | None = None,
        is_active: bool = True,
    ) -> Conversation:
        """Create a conversation with all parameters specified (low-level method).

        This is the primary low-level method for creating conversations. Higher-level
        services (like TaskPhaseTransitionService) should use this instead of
        constructing Conversation objects directly.

        Args:
            parent_entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
            parent_entity_id: ID of parent entity
            agent_role: Agent role for this conversation
            engine: Agent engine powering this conversation
            model_id: Model identifier (e.g., "anthropic:claude-sonnet-4")
            external_session_id: Optional external session ID for Claude Code/Gemini
            is_active: Whether this is the active conversation (default True)

        Returns:
            New Conversation instance
        """
        conversation = Conversation(
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            agent_role=agent_role.value,
            engine=engine,
            model_id=model_id,
            external_session_id=external_session_id,
            is_active=is_active,
        )

        self.db.add(conversation)
        self.db.flush()

        return conversation

    def update_model(self, conversation_id: int, model_id: str) -> Conversation:
        """Update the model for a conversation.

        Model can be changed within the same engine (e.g., Opus → Sonnet in Claude Code).

        Args:
            conversation_id: ID of conversation to update
            model_id: New model identifier

        Returns:
            Updated Conversation instance

        Raises:
            ValueError: If conversation not found
        """
        conversation = self.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.model_id = model_id
        self.db.flush()

        return conversation

    def get_active_for_entity(
        self,
        parent_type: ParentEntityType,
        parent_id: int,
    ) -> Conversation | None:
        """Get active conversation for an entity (alias for get_active_conversation_for_entity).

        Args:
            parent_type: Type of parent entity
            parent_id: ID of parent entity

        Returns:
            Active Conversation or None
        """
        return self.get_active_conversation_for_entity(parent_type, parent_id)

    def archive(self, conversation_id: int) -> None:
        """Archive a conversation (alias for archive_conversation).

        Args:
            conversation_id: ID of conversation to archive
        """
        self.archive_conversation(conversation_id)

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

    def update_external_session_id(self, conversation_id: int, session_id: str) -> None:
        """Update the external session ID for a conversation.

        Used by Claude Code and other external engines to persist session continuity.

        Args:
            conversation_id: ID of conversation to update
            session_id: New session ID from external engine
        """
        conversation = self.get_by_id(conversation_id)
        if conversation:
            conversation.external_session_id = session_id
            self.db.flush()

    # Message methods
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
        return result.rowcount

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

        return self.db.execute(stmt).rowcount

    def convert_messages_to_pydantic(self, message_records: list[ConversationMessage]) -> list[ModelMessage]:
        """Extract PydanticAI message history from database records."""
        # Extract pydantic_content from each record
        serialized_messages = [record.pydantic_content for record in message_records]

        if not serialized_messages:
            return []

        # Deserialize the messages
        messages = ModelMessagesTypeAdapter.validate_python(serialized_messages)
        return messages
