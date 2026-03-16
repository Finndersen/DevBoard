"""Claude Code project path cache model."""

import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ClaudeProjectPathCache(Base):
    """Maps Claude Code encoded project directory names to original filesystem paths."""

    __tablename__ = "claude_project_path_cache"

    encoded_path: Mapped[str] = mapped_column(String(512), primary_key=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )
