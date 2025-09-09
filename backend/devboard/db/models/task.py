"""Task-related database models."""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, task_context_resource_association
from .base_conversation import BaseConversationMessage

if TYPE_CHECKING:
    from .codebase import Codebase
    from .configuration import ContextProviderResource
    from .project import Project


class Task(Base):
    """Represents a single, self-contained piece of work within a project."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    codebase_id: Mapped[int | None] = mapped_column(ForeignKey("codebases.id"))

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="Pending")
    remote_task_id: Mapped[str | None] = mapped_column(String(100))
    conversation_id: Mapped[str | None] = mapped_column(String(100))
    implementation_plan: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC)
    )

    project: Mapped["Project"] = relationship(back_populates="tasks")
    codebase: Mapped["Codebase | None"] = relationship(back_populates="tasks")
    context_resources: Mapped[list["ContextProviderResource"]] = relationship(
        secondary=task_context_resource_association, back_populates="tasks"
    )
    messages: Mapped[list["TaskConversationMessage"]] = relationship(back_populates="task")


class TaskConversationMessage(BaseConversationMessage):
    """Represents a single message or tool call in the conversation with a Task Planning Agent."""

    __tablename__ = "task_conversation_messages"

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    task: Mapped["Task"] = relationship(back_populates="messages")
