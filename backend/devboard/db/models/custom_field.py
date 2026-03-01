"""Custom field definition database model."""

import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import EntityType


class CustomFieldType(StrEnum):
    """Enumeration of possible custom field types."""

    TEXT = "text"
    BOOLEAN = "boolean"
    ENUM = "enum"


class CustomFieldDefinition(Base):
    """Defines a custom field that can be associated with an entity type.

    Custom field definitions are scoped by entity type (task, project, codebase).
    Names must be unique within an entity type.
    """

    __tablename__ = "custom_field_definitions"
    __table_args__ = (UniqueConstraint("name", "entity_type", name="uq_custom_field_name_entity_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), nullable=False, default=EntityType.TASK)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type: Mapped[CustomFieldType] = mapped_column(Enum(CustomFieldType), nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
