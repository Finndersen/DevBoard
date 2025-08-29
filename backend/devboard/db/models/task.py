"""Task-related database models."""
import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Task(Base):
    """Represents a single, self-contained piece of work within a project."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    codebase_id: Mapped[Optional[int]] = mapped_column(ForeignKey("codebases.id"))

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="Pending")
    remote_task_id: Mapped[Optional[str]] = mapped_column(String(100))
    conversation_id: Mapped[Optional[str]] = mapped_column(String(100))
    implementation_plan: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    codebase: Mapped[Optional["Codebase"]] = relationship(back_populates="tasks")