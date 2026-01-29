"""Custom field definition database model."""

import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CustomFieldType(StrEnum):
    """Enumeration of possible custom field types."""

    TEXT = "text"
    BOOLEAN = "boolean"
    ENUM = "enum"


class CustomFieldDefinition(Base):
    """Defines a custom field that can be associated with tasks.

    Custom field definitions are global - shared across all projects/tasks.
    """

    __tablename__ = "custom_field_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type: Mapped[CustomFieldType] = mapped_column(Enum(CustomFieldType), nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
