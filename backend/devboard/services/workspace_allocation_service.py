"""Service for workspace allocation and worktree slot management.

Handles allocation of worktree slots to tasks with intelligent strategies:
- Task stickiness (prefer previously used slot)
- Branch optimization (use slot already on correct branch)
- LRU allocation (least recently used available slot)
"""

import asyncio
import datetime
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import logfire

from devboard.db.models import Codebase, Task, WorktreeSlot
from devboard.db.repositories.task import TaskRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitIntegration
from devboard.integrations.shell import ShellCommandExecutionError


class AllSlotsLockedException(Exception):
    """Raised when all worktree slots are locked and allocation fails."""

    pass


class WorkspaceAllocationService:
    """Service for workspace allocation and worktree slot management."""

    def __init__(
        self,
        worktree_slot_repo: WorktreeSlotRepository,
        task_repo: TaskRepository,
    ):
        """Initialize service.

        Args:
            worktree_slot_repo: Repository for worktree slot operations
            task_repo: Repository for task operations
        """
        self.worktree_slot_repo = worktree_slot_repo
        self.task_repo = task_repo

    async def slot_has_uncommitted_changes(self, slot: WorktreeSlot) -> bool:
        """Check if a worktree slot has uncommitted git changes."""
        git = GitIntegration(slot.path)
        has_changes = await git.has_uncommitted_changes()
        if has_changes:
            logfire.info(f"Slot {slot.id} at {slot.path} has uncommitted changes")
        return has_changes

    async def allocate_for_task(self, task: Task, use_main_slot: bool = False) -> WorktreeSlot:
        """Find an appropriate slot and lock it for a task.

        Implements smart allocation with:
        1. Task stickiness - prefer last-used slot
        2. Branch optimization - use slot already on base branch
        3. LRU - pick least recently used available slot

        Raises:
            ValueError: If task has invalid configuration
            AllSlotsLockedException: If no suitable slots are available
        """
        # Get all available (unlocked) slots for this codebase
        all_slots = self.worktree_slot_repo.get_by_codebase(task.codebase.id, include_main=use_main_slot)
        available_slots: list[WorktreeSlot] = [s for s in all_slots if not s.locked]

        if not available_slots:
            raise AllSlotsLockedException("All worktree slots are currently in use")

        # Always filter out slots with uncommitted changes
        clean_slots = []
        for slot in available_slots:
            has_changes = await self.slot_has_uncommitted_changes(slot)
            if not has_changes:
                clean_slots.append(slot)

        if not clean_slots:
            # All unlocked slots are dirty
            raise AllSlotsLockedException("All available slots have uncommitted changes")

        available_slots = clean_slots

        # Strategy 1: Task stickiness - prefer last-used slot
        slot: WorktreeSlot
        for slot in available_slots:
            if slot.last_used_by_task_id == task.id:
                logfire.info(f"Using sticky slot {slot.id} for task {task.id}")
                return self.worktree_slot_repo.lock_slot(slot, task)

        # Strategy 2: Branch optimization - slot already on base branch
        for slot in available_slots:
            current_branch = await asyncio.to_thread(slot.get_current_branch)
            if current_branch is not None and current_branch == task.base_branch:
                logfire.info(
                    f"Using optimized slot {slot.id} (already on branch {task.base_branch}) for task {task.id}"
                )
                return self.worktree_slot_repo.lock_slot(slot, task)

        # Strategy 3: LRU - least recently used slot
        lru_slot: WorktreeSlot = min(available_slots, key=lambda s: s.last_used_at)
        logfire.info(f"Using LRU slot {lru_slot.id} for task {task.id}")
        return self.worktree_slot_repo.lock_slot(lru_slot, task)

    async def checkout_branch_in_slot(self, slot: WorktreeSlot, branch_name: str) -> None:
        """Checkout a branch in a slot if it's not already on that branch.

        Args:
            slot: WorktreeSlot to checkout branch in
            branch_name: Name of branch to checkout

        Raises:
            ValueError: If git operations fail
        """
        # Get current branch dynamically
        current_branch = await asyncio.to_thread(slot.get_current_branch)

        # Checkout branch if different
        if current_branch != branch_name:
            logfire.info(f"Checking out branch {branch_name} in slot {slot.id}")
            git = GitIntegration(slot.path)
            try:
                await git.checkout_branch(branch_name)
            except ShellCommandExecutionError as e:
                error_msg = e.stderr if hasattr(e, "stderr") else str(e)
                raise ValueError(f"Failed to checkout branch {branch_name}: {error_msg}") from e
        else:
            logfire.info(f"Slot {slot.id} already on branch {branch_name}, skipping checkout")

    def codebase_slot_count(self, codebase_id: int) -> int:
        slots = self.worktree_slot_repo.get_by_codebase(codebase_id)
        return len(slots)

    def release_slot(self, slot: WorktreeSlot) -> None:
        self.worktree_slot_repo.unlock_slot(slot)
        logfire.info(f"Released slot {slot.id}")

    async def create_and_lock_slot(self, task: Task, use_main_slot: bool = False) -> WorktreeSlot:
        """Create a new worktree slot and lock it for a task."""
        # Ensure main repo slot exists before creating worktree slots
        main_slot = self.bootstrap_main_repo_slot(task.codebase)

        if use_main_slot and not self.slot_has_uncommitted_changes(main_slot):
            self.worktree_slot_repo.lock_slot(main_slot, task)
            return main_slot

        # Generate worktree path
        worktree_path = self._generate_new_worktree_path(task.codebase)

        # Determine branch for worktree creation (use base_branch as default)
        branch_for_worktree = task.branch_name or task.base_branch

        # Create the worktree
        git = GitIntegration(task.codebase.local_path)
        logfire.info(f"Creating worktree at {worktree_path} for task {task.id} on branch {branch_for_worktree}")
        await git.create_worktree(worktree_path, branch_for_worktree)

        # Create slot in database
        slot = self.worktree_slot_repo.create(
            codebase_id=task.codebase.id,
            path=worktree_path,
            is_main_repo=False,
        )

        # Lock the slot
        return self.worktree_slot_repo.lock_slot(slot, task)

    def _generate_new_worktree_path(self, codebase: Codebase) -> str:
        """Generate a unique worktree path as sibling to main repo.

        Args:
            codebase: The codebase instance

        Returns:
            Path for the new worktree
        """
        path = Path(codebase.local_path)
        parent = path.parent
        base_name = path.name

        # Get next slot number based on existing slots
        # Total slots includes main repo (slot 0), so count gives us the next slot number
        slot_number = self.codebase_slot_count(codebase.id)
        worktree_path = parent / f"{base_name}.worktree-{slot_number}"
        return str(worktree_path)

    async def cleanup_stale_locks(self, codebase_id: int | None = None) -> int:
        """Cleanup stale locks for tasks with no active conversations.

        Args:
            codebase_id: Optional codebase ID to filter by

        Returns:
            Number of locks released
        """
        locked_slots = self.worktree_slot_repo.get_all_locked_for_codebase(codebase_id=codebase_id)
        released_count = 0

        for slot in locked_slots:
            # Check age-based failsafe (24 hours based on last_used_at)
            age = datetime.datetime.now(datetime.UTC) - slot.last_used_at
            if age > datetime.timedelta(hours=2):
                logfire.warn(
                    f"Releasing very old lock on slot {slot.id} (task {slot.last_used_by_task_id}, "
                    f"last used {age.total_seconds() / 3600:.1f}h ago)"
                )
                self.worktree_slot_repo.unlock_slot(slot)
                released_count += 1

        return released_count

    def bootstrap_main_repo_slot(self, codebase: Codebase) -> WorktreeSlot:
        """Create the main repository slot (slot 0) if it doesn't exist."""
        # Check if any slot with the main repo path exists
        existing_main = self.worktree_slot_repo.get_by_path(codebase.id, codebase.local_path)
        if existing_main:
            return existing_main

        # Create main repo slot (current_branch will be determined dynamically)
        logfire.info(f"Bootstrapping main repo slot for codebase {codebase.id}")
        return self.worktree_slot_repo.create(
            codebase_id=codebase.id,
            path=codebase.local_path,
            is_main_repo=True,
        )

    @asynccontextmanager
    async def allocate_workspace(
        self,
        task: Task,
        max_worktrees: int | None = None,
        use_main_slot: bool = False,
    ) -> AsyncIterator[WorktreeSlot]:
        """Allocate and manage a workspace for a task.

        This context manager handles the complete workspace lifecycle:
        1. Finds an appropriate free workspace and locks it
        2. Checks out the task's base branch
        3. Yields the workspace path for use
        4. Unlocks the workspace on exit (success or failure)

        Args:
            task: The task requiring a workspace
            max_worktrees: Optional maximum number of worktrees allowed
            use_main_slot: Whether to use the main repo slot if available

        Yields:
            WorktreeSlot instance allocated for the task

        Raises:
            ValueError: If task has invalid configuration
            AllSlotsLockedException: If max_worktrees limit reached
        """
        slot: WorktreeSlot | None = None

        try:
            # Try to allocate an existing slot
            try:
                slot = await self.allocate_for_task(task, use_main_slot=use_main_slot)
            except AllSlotsLockedException:
                # Check if we've reached the max worktree limit
                if max_worktrees is not None:
                    total_slots = self.codebase_slot_count(task.codebase.id)
                    if total_slots >= max_worktrees:
                        logfire.warn(f"Max worktrees ({max_worktrees}) reached for codebase {task.codebase.id}")
                        raise

                # Create a new slot
                logfire.info(f"All slots locked, creating new worktree for task {task.id}")
                slot = await self.create_and_lock_slot(task, use_main_slot=use_main_slot)

            # Checkout base branch in the allocated slot
            await self.checkout_branch_in_slot(slot, task.base_branch)

            # Yield the workspace path for use
            logfire.info(f"Allocated workspace {slot.path} for task {task.id}")
            yield slot

        finally:
            # Always unlock the slot on exit
            if slot:
                self.release_slot(slot)
                logfire.info(f"Released workspace {slot.path} for task {task.id}")
