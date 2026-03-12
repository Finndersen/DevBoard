"""Repository for worktree slot data access operations."""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from devboard.db.models import WorktreeSlot
from devboard.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from devboard.db.models import Task


class WorktreeSlotRepository(BaseRepository[WorktreeSlot]):
    """Repository for worktree slot data access operations."""

    def create(
        self,
        codebase_id: int,
        path: str,
        is_main_repo: bool = False,
    ) -> WorktreeSlot:
        """Create a new worktree slot.

        Args:
            codebase_id: ID of the codebase this slot belongs to
            path: Filesystem path to the worktree
            is_main_repo: Whether this is the main repository (slot 0)

        Returns:
            Created WorktreeSlot instance
        """
        slot = WorktreeSlot(
            codebase_id=codebase_id,
            path=path,
            is_main_repo=is_main_repo,
            last_used_at=datetime.datetime.now(datetime.UTC),
        )
        self.db.add(slot)
        self.db.flush()
        return slot

    def get_by_id(self, slot_id: int) -> WorktreeSlot | None:
        """Get a worktree slot by ID.

        Args:
            slot_id: The slot ID to search for

        Returns:
            WorktreeSlot instance if found, None otherwise
        """
        stmt = select(WorktreeSlot).where(WorktreeSlot.id == slot_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_codebase(self, codebase_id: int, include_main: bool = True) -> list[WorktreeSlot]:
        """Get all worktree slots for a codebase.

        Args:
            codebase_id: The codebase ID to get slots for
            include_main: Whether to include the main repo slot (slot 0)

        Returns:
            List of WorktreeSlot instances
        """
        stmt = (
            select(WorktreeSlot)
            .where(WorktreeSlot.codebase_id == codebase_id)
            .options(joinedload(WorktreeSlot.last_used_by_task))
            .order_by(WorktreeSlot.created_at.asc())
        )
        if not include_main:
            stmt = stmt.where(WorktreeSlot.is_main_repo.is_(False))
        return list(self.db.execute(stmt).scalars().all())

    def find_one(
        self,
        codebase_id: int,
        locked: bool | None = None,
        last_used_by_task_id: int | None = None,
    ) -> WorktreeSlot | None:
        """Find a single worktree slot matching criteria.

        Used for allocation strategies (stickiness).

        Args:
            codebase_id: The codebase ID to search in
            locked: Filter by locked status (None means don't filter by lock status)
            last_used_by_task_id: Filter by last used task ID

        Returns:
            First matching WorktreeSlot or None
        """
        stmt = select(WorktreeSlot).where(WorktreeSlot.codebase_id == codebase_id)

        # Filter by locked status if specified
        if locked is not None:
            stmt = stmt.where(WorktreeSlot.locked == locked)

        if last_used_by_task_id is not None:
            stmt = stmt.where(WorktreeSlot.last_used_by_task_id == last_used_by_task_id)

        stmt = stmt.options(joinedload(WorktreeSlot.last_used_by_task))

        return self.db.execute(stmt).scalar_one_or_none()

    def find_oldest_available(self, codebase_id: int) -> WorktreeSlot | None:
        """Find the least recently used available slot (LRU strategy).

        Args:
            codebase_id: The codebase ID to search in

        Returns:
            Oldest available WorktreeSlot or None if all locked
        """
        stmt = (
            select(WorktreeSlot)
            .where(WorktreeSlot.codebase_id == codebase_id, WorktreeSlot.locked.is_(False))
            .options(joinedload(WorktreeSlot.last_used_by_task))
            .order_by(WorktreeSlot.last_used_at.asc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all_locked(self, codebase_id: int | None = None) -> list[WorktreeSlot]:
        """Get all locked worktree slots, optionally filtered by codebase."""
        stmt = (
            select(WorktreeSlot)
            .where(WorktreeSlot.locked.is_(True))
            .options(joinedload(WorktreeSlot.last_used_by_task))
        )
        if codebase_id is not None:
            stmt = stmt.where(WorktreeSlot.codebase_id == codebase_id)

        return list(self.db.execute(stmt).scalars().all())

    def lock_slot(
        self,
        slot: WorktreeSlot,
        task: "Task",
    ) -> WorktreeSlot:
        """Lock a slot for a task.

        Args:
            slot: The slot to lock
            task: The task locking the slot

        Returns:
            Updated WorktreeSlot instance
        """
        slot.locked = True
        slot.last_used_at = datetime.datetime.now(datetime.UTC)
        slot.last_used_by_task = task

        self.db.flush()
        return slot

    def unlock_slot(self, slot: WorktreeSlot) -> WorktreeSlot:
        """Unlock a slot, making it available for reuse.

        Args:
            slot: The slot to unlock

        Returns:
            Updated WorktreeSlot instance
        """
        slot.locked = False
        # Keep last_used_at and last_used_by_task_id for stickiness optimization

        self.db.flush()
        return slot

    def assign_slot(self, slot: WorktreeSlot, task: "Task") -> WorktreeSlot:
        """Assign a slot to a task for sticky tracking without locking.

        This sets the last_used_by_task_id for sticky slot allocation but does NOT
        lock the slot. Use this for operations like checkout_task_to_main_repo where
        we want to track which task is using a slot but the slot should remain
        available for the agent to lock when it actually runs.

        Args:
            slot: The slot to assign
            task: The task to assign to

        Returns:
            Updated WorktreeSlot instance
        """
        slot.last_used_at = datetime.datetime.now(datetime.UTC)
        slot.last_used_by_task = task

        self.db.flush()
        return slot

    def update(self, slot: WorktreeSlot) -> WorktreeSlot:
        """Update a worktree slot.

        Args:
            slot: WorktreeSlot instance to update

        Returns:
            Updated WorktreeSlot
        """
        self.db.merge(slot)
        self.db.flush()
        return slot

    def delete(self, slot: WorktreeSlot) -> None:
        """Delete a worktree slot.

        Args:
            slot: The slot to delete
        """
        self.db.delete(slot)
        self.db.flush()

    def get_by_path(self, path: str) -> WorktreeSlot | None:
        """Get a worktree slot by its path.

        Args:
            codebase_id: The codebase ID
            path: The filesystem path

        Returns:
            WorktreeSlot instance if found, None otherwise
        """
        stmt = select(WorktreeSlot).where(WorktreeSlot.path == path)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_last_used_slot_for_task(self, task_id: int) -> WorktreeSlot | None:
        """Get the most recently used worktree slot for a task.

        Finds the slot with last_used_by_task_id equal to the task ID
        and the latest last_used_at timestamp.

        Args:
            task_id: The task ID to search for

        Returns:
            WorktreeSlot instance if found, None otherwise
        """
        stmt = (
            select(WorktreeSlot)
            .where(WorktreeSlot.last_used_by_task_id == task_id)
            .order_by(WorktreeSlot.last_used_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_main_slot_for_codebase(self, codebase_id: int) -> WorktreeSlot:
        """Get the main repository slot for a codebase.

        Args:
            codebase_id: The codebase ID to search for

        Returns:
            WorktreeSlot instance for the main repo

        Raises:
            ValueError: If no main repo slot exists for the codebase
        """
        stmt = select(WorktreeSlot).where(
            WorktreeSlot.codebase_id == codebase_id,
            WorktreeSlot.is_main_repo.is_(True),
        )
        slot = self.db.execute(stmt).scalar_one_or_none()
        if slot is None:
            raise ValueError(f"No main repo slot found for codebase {codebase_id}")
        return slot
