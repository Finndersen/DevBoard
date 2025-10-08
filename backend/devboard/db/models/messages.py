"""Conversation message model."""

import datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_core import to_jsonable_python
from sqlalchemy import JSON, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .conversation import Conversation


class MessageType(StrEnum):
    # Request types
    USER_PROMPT = auto()
    TOOL_RESULT = auto()
    # Response types
    TOOL_CALL = auto()
    TEXT_RESPONSE = auto()
    STRUCTURED_RESPONSE = auto()


def _get_message_type(message: ModelMessage) -> MessageType:
    if isinstance(message, ModelRequest):
        if any(isinstance(part, UserPromptPart) for part in message.parts):
            return MessageType.USER_PROMPT
        else:
            # Could also be a SystemPromptPart, but we are not storing those, or a RetryPromptPart
            return MessageType.TOOL_RESULT
    else:
        if isinstance(message.parts[-1], ToolCallPart) and message.parts[-1].tool_name == "final_result":
            return MessageType.STRUCTURED_RESPONSE
        elif any(isinstance(part, ToolCallPart) for part in message.parts):
            return MessageType.TOOL_CALL
        elif any(isinstance(part, TextPart) for part in message.parts):
            return MessageType.TEXT_RESPONSE
        else:
            raise ValueError(f"Cannot determine message type for response message with parts: {message.parts}")


class ConversationMessage(Base):
    """Represents a single message in an agent conversation.

    Stores PydanticAI ModelRequest and ModelResponse messages in JSON format
    with minimal metadata for efficient storage and retrieval.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))

    # Simple message type indicator
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType))

    # Full serialized PydanticAI message content (ModelRequest or ModelResponse)
    pydantic_content: Mapped[dict[str, Any]] = mapped_column(JSON)

    # Text content for display (can differ from computed value)
    text_content: Mapped[str]

    timestamp: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationship
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    @classmethod
    def from_pydantic_message(cls, conversation_id: int, message: ModelMessage) -> "ConversationMessage":
        """Construct a message model from a Pydantic Request or Response message."""
        message_type = _get_message_type(message)

        # Extract text content based on message type
        text_content = ""
        for part in message.parts:
            if isinstance(part, TextPart | UserPromptPart):
                text_content += part.content

        return cls(
            conversation_id=conversation_id,
            message_type=message_type,
            pydantic_content=to_jsonable_python(message),
            text_content=text_content,
        )
