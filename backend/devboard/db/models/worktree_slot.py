"""Worktree slot database model."""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from devboard.integrations.git import GitRepoIntegration

from .base import Base

if TYPE_CHECKING:
    from .codebase import Codebase
    from .task import Task


class WorktreeSlot(Base):
    """Represents a slot in the worktree pool for a codebase.

    Each slot represents a working directory (either the main repository or a worktree)
    that can be allocated to tasks. Slots can be locked by tasks when agents are running,
    and are tracked for stickiness (tasks prefer to reuse the same slot).
    """

    __tablename__ = "worktree_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    codebase_id: Mapped[int] = mapped_column(ForeignKey("codebases.id"))
    path: Mapped[str] = mapped_column(String(512))
    is_main_repo: Mapped[bool] = mapped_column(Boolean, default=False)

    # Lock state
    locked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Usage tracking (doubles as lock history when locked=False)
    last_used_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
    last_used_by_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))

    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationships
    codebase: Mapped["Codebase"] = relationship(back_populates="worktree_slots")
    last_used_by_task: Mapped["Task | None"] = relationship(
        foreign_keys=[last_used_by_task_id], back_populates="worktree_slots"
    )

    async def get_current_branch(self) -> str | None:
        """Get the current git branch for this worktree slot.

        Returns:
            Current branch name, or None if unable to determine
        """
        git = GitRepoIntegration(self.path)
        # Run the async method synchronously
        return await git.get_current_branch()
