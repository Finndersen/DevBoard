"""Configuration-related database models."""

import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Configuration(Base):
    """Generic key-value configuration store for all application settings."""

    __tablename__ = "configurations"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[str] = mapped_column(String(50), default="1.0")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
