"""Language model database model."""

import datetime

from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from devboard.agents.language_models import LLMProvider, ModelType

from .base import Base


class LanguageModelDB(Base):
    """Database model for language model definitions."""

    __tablename__ = "language_models"
    __table_args__ = (UniqueConstraint("provider", "name", name="uq_language_model_provider_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[LLMProvider] = mapped_column(Enum(LLMProvider))
    name: Mapped[str] = mapped_column(String(255))
    model_type: Mapped[ModelType] = mapped_column(Enum(ModelType))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bedrock_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    context_window: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    @property
    def model_id(self) -> str:
        return f"{self.provider}:{self.name}"

    @property
    def display_full_name(self) -> str:
        """Full model identifier for external engines, falls back to name."""
        return self.full_name if self.full_name else self.name
