"""Repository for conversation and message data access operations."""

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from sqlalchemy import delete, select

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
