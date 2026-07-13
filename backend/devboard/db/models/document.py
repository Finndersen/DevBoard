"""Document model for storing various text documents in the system."""

import datetime
from enum import StrEnum

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DocumentType(StrEnum):
    """Types of documents in the system."""

    PROJECT_SPECIFICATION = "project_specification"
    INITIATIVE_CONTEXT = "initiative_context"
    TASK_SPECIFICATION = "task_specification"
    TASK_IMPLEMENTATION_PLAN = "task_implementation_plan"
    CHANGE_SUMMARY = "change_summary"


class Document(Base):
    """Generic document storage with content hashing for conflict detection."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType))  # Store enum as string
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(32))  # MD5 hash (32 hex chars)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
