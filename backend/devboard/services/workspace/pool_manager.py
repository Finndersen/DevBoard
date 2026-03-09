"""Worktree pool manager for allocating, releasing and managing worktree slots."""

import datetime
import os
from pathlib import Path

import logfire

from devboard.db.models import Codebase, Task, WorktreeSlot
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import ShellCommandExecutionError
from devboard.services.workspace.types import (
    AllSlotsLockedException,
    BranchInUseException,
    LastUsedByTaskInfo,
    LockedByTaskInfo,
    PoolStats,
    PoolStatus,
    SlotInfo,
)


class WorktreePoolManager:
    """Manages the pool of worktree slots for a codebase."""

    def __init__(self, worktree_slot_repo: WorktreeSlotRepository, worktree_directory: str = "central"):
        self.worktree_slot_repo = worktree_slot_repo
        self.worktree_directory = worktree_directory

    def bootstrap_main_repo_slot(self, codebase: Codebase) -> WorktreeSlot:
        """Create the main repository slot (slot 0) if it doesn't exist."""
        existing_main = self.worktree_slot_repo.get_by_path(codebase.local_path)
        if existing_main:
            return existing_main

        logfire.info(f"Bootstrapping main repo slot for codebase {codebase.id}")
        return self.worktree_slot_repo.create(
            codebase_id=codebase.id,
            path=codebase.local_path,
            is_main_repo=True,
        )

    def _generate_new_worktree_path(self, codebase: Codebase) -> str:
        """Generate a unique worktree path based on the configured worktree_directory setting."""
        repo_path = Path(codebase.local_path)
        repo_name = repo_path.name
        slot_number = len(self.worktree_slot_repo.get_by_codebase(codebase.id))

        if self.worktree_directory == "alongside":
            worktree_path = repo_path.parent / f"{repo_name}.worktree-{slot_number}"
        else:
            # Default: central mode — place under DEVBOARD_HOME/worktrees/
            devboard_home = Path(os.environ.get("DEVBOARD_HOME", str(Path.home() / ".devboard")))
            central_base = devboard_home / "worktrees"
            central_base.mkdir(parents=True, exist_ok=True)
            worktree_path = central_base / f"{codebase.id}_{repo_name}.worktree-{slot_number}"

        return str(worktree_path)

    async def _create_worktree_for_slot(self, slot: WorktreeSlot, task: Task) -> None:
        """Create a git worktree for a slot."""
        logfire.warn(f"Creating worktree for slot {slot.id} at {slot.path}")
        git = GitRepoIntegration(task.codebase.local_path)
        await git.create_worktree(slot.path, task.branch_name)

    def codebase_slot_count(self, codebase_id: int) -> int:
        slots = self.worktree_slot_repo.get_by_codebase(codebase_id)
        return len(slots)

    def release_slot(self, slot: WorktreeSlot) -> None:
        self.worktree_slot_repo.unlock_slot(slot)
        self.worktree_slot_repo.commit()
        logfire.info(f"Released slot {slot.id}")

    async def slot_has_uncommitted_changes(self, slot: WorktreeSlot) -> bool:
        """Check if a worktree slot has uncommitted git changes."""
        git = GitRepoIntegration(slot.path)
        return await git.has_uncommitted_changes()

    async def cleanup_stale_locks(self, codebase_id: int | None = None) -> int:
        """Cleanup stale locks for tasks with no active conversations.

        Returns:
            Number of locks released
        """
        locked_slots = self.worktree_slot_repo.get_all_locked(codebase_id=codebase_id)
        released_count = 0

        for slot in locked_slots:
            last_used = slot.last_used_at.replace(tzinfo=datetime.UTC)
            age = datetime.datetime.now(datetime.UTC) - last_used
            if age > datetime.timedelta(minutes=30):
                logfire.warn(
                    f"Releasing very old lock on slot {slot.id} (task {slot.last_used_by_task_id}, "
                    f"last used {age.total_seconds() / 3600:.1f}h ago)"
                )
                self.worktree_slot_repo.unlock_slot(slot)
                released_count += 1

        return released_count

    async def allocate_for_task(self, task: Task) -> WorktreeSlot:
        """Find an appropriate slot and lock it for a task.

        Implements smart allocation with priority:
        1. Branch location - slot already has task's branch checked out
        2. Task stickiness - prefer last-used slot
        3. LRU - pick least recently used available slot

        Raises:
            ValueError: If task has no branch name configured
            AllSlotsLockedException: If no suitable slots are available
            BranchInUseException: If branch is already locked by another task
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch configured")

        await self.cleanup_stale_locks(codebase_id=task.codebase.id)

        include_main_in_pool = task.codebase.max_worktrees == 0

        if include_main_in_pool:
            self.bootstrap_main_repo_slot(task.codebase)

        all_slots = self.worktree_slot_repo.get_by_codebase(task.codebase.id, include_main=True)
        all_slots_sorted = sorted(all_slots, key=lambda s: s.last_used_at, reverse=True)

        # PRIORITY 1: Check if task's branch is already checked out in any available slot
        git = GitRepoIntegration(task.codebase.local_path)
        branch_location = await git.get_checked_out_location(task.branch_name)

        if branch_location:
            normalized_branch_location = str(Path(branch_location).resolve())
            for slot in all_slots_sorted:
                normalized_slot_path = str(Path(slot.path).resolve())
                if normalized_slot_path == normalized_branch_location:
                    if not slot.locked:
                        logfire.info(
                            f"Using slot {slot.id} for task {task.id} - branch {task.branch_name} already checked out there"
                        )
                        return self.worktree_slot_repo.lock_slot(slot, task)
                    else:
                        if slot.last_used_by_task_id == task.id:
                            logfire.warn(
                                f"Re-acquiring stale lock on slot {slot.id} for task {task.id} "
                                f"(branch {task.branch_name} already checked out there)"
                            )
                            return self.worktree_slot_repo.lock_slot(slot, task)
                        raise BranchInUseException(
                            f"Branch '{task.branch_name}' is already in use by task {slot.last_used_by_task_id}"
                        )

        # PRIORITY 2: Sticky slot and candidate pool in single pass
        sticky_slot: WorktreeSlot | None = None
        candidate_slots: list[WorktreeSlot] = []

        for slot in all_slots_sorted:
            if slot.locked:
                continue

            if slot.last_used_by_task_id == task.id:
                if slot.is_main_repo:
                    current_branch = await slot.get_current_branch()
                    if current_branch != task.branch_name:
                        logfire.info(
                            f"Skipping main repo sticky slot {slot.id} for task {task.id}: "
                            f"branch mismatch (current={current_branch}, task={task.branch_name})"
                        )
                    else:
                        sticky_slot = slot
                        break
                else:
                    sticky_slot = slot
                    break

            if include_main_in_pool or not slot.is_main_repo:
                candidate_slots.append(slot)

        if sticky_slot:
            logfire.info(f"Using sticky slot {sticky_slot.id} for task {task.id}")
            return self.worktree_slot_repo.lock_slot(sticky_slot, task)

        if not candidate_slots:
            raise AllSlotsLockedException("All worktree slots are currently in use")

        # PRIORITY 3: LRU among clean slots
        best_slot: WorktreeSlot | None = None
        for slot in candidate_slots:
            if await self.slot_has_uncommitted_changes(slot):
                logfire.info(f"Slot {slot.id} at {slot.path} has uncommitted changes")
                continue
            if best_slot is None or slot.last_used_at < best_slot.last_used_at:
                best_slot = slot

        if not best_slot:
            raise AllSlotsLockedException("All available slots have uncommitted changes")

        logfire.info(f"Using LRU slot {best_slot.id} for task {task.id}")
        return self.worktree_slot_repo.lock_slot(best_slot, task)

    async def create_and_lock_slot(self, task: Task) -> WorktreeSlot:
        """Create a new worktree slot and lock it for a task."""
        self.bootstrap_main_repo_slot(task.codebase)

        worktree_path = self._generate_new_worktree_path(task.codebase)

        slot = self.worktree_slot_repo.create(
            codebase_id=task.codebase.id,
            path=worktree_path,
            is_main_repo=False,
        )

        logfire.info(f"Creating worktree at {worktree_path} for task {task.id}")
        await self._create_worktree_for_slot(slot, task)

        return self.worktree_slot_repo.lock_slot(slot, task)

    async def delete_worktree_slot(self, slot: WorktreeSlot, force: bool = False) -> None:
        """Delete a worktree slot and its associated worktree.

        Raises:
            ValueError: If slot is main repo, locked (and not forced), or git fails
        """
        if slot.is_main_repo:
            raise ValueError("Cannot delete main repository slot")

        if slot.locked and not force:
            raise ValueError(f"Slot {slot.id} is currently locked")

        codebase = slot.codebase

        if Path(slot.path).exists():
            git = GitRepoIntegration(codebase.local_path)
            try:
                await git.remove_worktree(slot.path, force=force)
                logfire.info(f"Removed worktree at {slot.path}")
            except ShellCommandExecutionError as e:
                error_msg = e.stderr if hasattr(e, "stderr") else str(e)
                raise ValueError(f"Failed to remove worktree at {slot.path}: {error_msg}") from e

        self.worktree_slot_repo.delete(slot)
        logfire.info(f"Deleted worktree slot {slot.id}")

    async def get_pool_status_for_codebase(self, codebase: Codebase) -> PoolStatus:
        """Get status of all worktree slots for a codebase."""
        slots = self.worktree_slot_repo.get_by_codebase(codebase.id)

        slot_data: list[SlotInfo] = []
        available_count = 0
        locked_count = 0

        for slot in slots:
            if slot.locked:
                locked_count += 1
            else:
                available_count += 1

            current_branch = await slot.get_current_branch()

            locked_by_task = None
            last_used_by_task = None

            if slot.locked and slot.last_used_by_task:
                locked_by_task = LockedByTaskInfo(
                    id=slot.last_used_by_task.id,
                    title=slot.last_used_by_task.title,
                )
            elif not slot.locked and slot.last_used_by_task:
                last_used_by_task = LastUsedByTaskInfo(
                    id=slot.last_used_by_task.id,
                    title=slot.last_used_by_task.title,
                )

            slot_data.append(
                SlotInfo(
                    id=slot.id,
                    path=slot.path,
                    is_main_repo=slot.is_main_repo,
                    status="locked" if slot.locked else "available",
                    current_branch=current_branch,
                    last_used_at=slot.last_used_at.isoformat() if slot.last_used_at else None,
                    locked_by_task=locked_by_task,
                    last_used_by_task=last_used_by_task,
                )
            )

        stats = PoolStats(
            total_slots=len(slots),
            available=available_count,
            locked=locked_count,
        )

        return PoolStatus(
            codebase_id=codebase.id,
            codebase_path=codebase.local_path,
            slots=slot_data,
            stats=stats,
        )
