"""Configuration-related database models."""
import datetime
from typing import Optional

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
        default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


class ContextProviderLink(Base):
    """Links a Project or Task to a specific Context Provider resource."""
    __tablename__ = "context_provider_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(255))  # References context provider by name
    parent_id: Mapped[int] = mapped_column()
    parent_type: Mapped[str] = mapped_column(String(50))  # 'project' or 'task'
    resource_uri: Mapped[str] = mapped_column(String(1024))
    description: Mapped[Optional[str]] = mapped_column(String(1024))  # User-provided or auto-generated
    auto_generated_description: Mapped[bool] = mapped_column(default=True)  # Track if description was auto-generated