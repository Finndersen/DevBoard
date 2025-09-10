"""Base conversation message model for inheritance."""

import datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING

from pydantic_ai.messages import ModelMessage, ModelRequest, TextPart, ToolCallPart, UserPromptPart
from pydantic_core import to_jsonable_python
from sqlalchemy import JSON, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .project import Project
    from .task import Task


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
        if any(isinstance(part, TextPart) for part in message.parts):
            return MessageType.TEXT_RESPONSE
        elif isinstance(message.parts[-1], ToolCallPart) and message.parts[-1].tool_name == "final_result":
            return MessageType.STRUCTURED_RESPONSE
        else:
            return MessageType.TOOL_CALL


class BaseConversationMessage(Base):
    """Abstract base class for conversation messages.

    Stores PydanticAI ModelRequest and ModelResponse messages in JSON format
    with minimal metadata for efficient storage and retrieval.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: int

    # Simple message type indicator: 'user_message',
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType))

    # Full serialized PydanticAI message content (ModelRequest or ModelResponse)
    pydantic_content: Mapped[dict[str, str]] = mapped_column(JSON)

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    @classmethod
    def from_pydantic_message(cls, entity_id: int, message: ModelMessage) -> "BaseConversationMessage":
        """Construct a message model from a Pydantic Request or Response message."""
        return cls(
            parent_id=entity_id,
            message_type=_get_message_type(message),
            pydantic_content=to_jsonable_python(message),
        )

class TaskConversationMessage(BaseConversationMessage):
    """Represents a single message or tool call in the conversation with a Task Planning Agent."""

    __tablename__ = "task_conversation_messages"

    parent_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    task: Mapped["Task"] = relationship(back_populates="messages")


class ProjectConversationMessage(BaseConversationMessage):
    """Represents a single message or tool call in the conversation with a Project Q&A Agent."""

    __tablename__ = "project_conversation_messages"

    parent_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    project: Mapped["Project"] = relationship(back_populates="messages")
