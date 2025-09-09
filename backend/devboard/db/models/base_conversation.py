"""Base conversation message model for inheritance."""

import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BaseConversationMessage(Base):
    """Abstract base class for conversation messages.

    Provides common fields for all conversation message types.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)

    # The role of the message sender, e.g., 'user', 'assistant', 'tool_call', 'tool_result'
    role: Mapped[str] = mapped_column(String(50))

    # For text content from 'user' or 'assistant'
    content: Mapped[str | None] = mapped_column(Text)

    # For structured data from 'tool_call' or 'tool_result'
    tool_data: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )
