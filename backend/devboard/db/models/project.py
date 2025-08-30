"""Project-related database models."""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, project_codebase_association

if TYPE_CHECKING:
    from .codebase import Codebase
    from .task import Task


class Project(Base):
    """Represents a high-level project, acting as a container for tasks and codebases."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    details: Mapped[str] = mapped_column(Text)
    current_status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
    codebases: Mapped[list["Codebase"]] = relationship(
        secondary=project_codebase_association, back_populates="projects"
    )
    messages: Mapped[list["ProjectConversationMessage"]] = relationship(back_populates="project")


class ProjectConversationMessage(Base):
    """Represents a single message or tool call in the conversation with a Project Q&A Agent."""

    __tablename__ = "project_conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))

    # The role of the message sender, e.g., 'user', 'assistant', 'tool_call', 'tool_result'
    role: Mapped[str] = mapped_column(String(50))

    # For text content from 'user' or 'assistant'
    content: Mapped[str | None] = mapped_column(Text)

    # For structured data from 'tool_call' or 'tool_result'
    tool_data: Mapped[dict | None] = mapped_column(Text)  # JSON stored as text

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    project: Mapped["Project"] = relationship(back_populates="messages")
