"""Service for workspace allocation and worktree slot management.

Handles allocation of worktree slots to tasks with intelligent strategies:
- Task stickiness (prefer previously used slot)
- Branch optimization (use slot already on correct branch)
- LRU allocation (least recently used available slot)
"""

import datetime
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import logfire

from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType
from devboard.db.models import Codebase, Task, WorktreeSlot
from devboard.db.models.task import NoWorktreeAllocatedException
from devboard.db.repositories.task import TaskRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import ShellCommandExecutionError
from devboard.services.task_git_service import TaskGitService


@dataclass
class LockedByTaskInfo:
    """Information about the task that has locked a slot."""

    id: int
    title: str
    branch: str | None


@dataclass
class SlotInfo:
    """Information about a worktree slot."""

    id: int
    path: str
    is_main_repo: bool
    status: Literal["locked", "available"]
    current_branch: str | None
    last_used_at: str | None
    locked_by_task: LockedByTaskInfo | None = None


@dataclass
class PoolStats:
    """Statistics about the worktree pool."""

    total_slots: int
    available: int
    locked: int


@dataclass
class PoolStatus:
    """Status of all worktree slots for a codebase."""

    codebase_id: int
    codebase_path: str
    slots: list[SlotInfo]
    stats: PoolStats


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
        self.task_git_service = TaskGitService(task_repo=task_repo, worktree_slot_repo=worktree_slot_repo)

    async def slot_has_uncommitted_changes(self, slot: WorktreeSlot) -> bool:
        """Check if a worktree slot has uncommitted git changes."""
        git = GitRepoIntegration(slot.path)
        has_changes = await git.has_uncommitted_changes()
        return has_changes

    async def allocate_for_task(self, task: Task, use_main_slot: bool = False) -> WorktreeSlot:
        """Find an appropriate slot and lock it for a task.

        Implements smart allocation with:
        1. Task stickiness - prefer last-used slot (with special handling for main repo)
        2. LRU - pick least recently used available slot

        For main repo slots:
        - Main repo slot is only reused for a task if the task's branch is still checked out there
        - If main repo has a different branch checked out, the task is allocated a different slot
        - This ensures main repo slot assignment only happens through explicit manual action

        Raises:
            ValueError: If task has invalid configuration
            AllSlotsLockedException: If no suitable slots are available
        """
        # Clean up any stale locks before attempting allocation
        await self.cleanup_stale_locks(codebase_id=task.codebase.id)

        # Get all available (unlocked) slots for this codebase
        all_slots = self.worktree_slot_repo.get_by_codebase(task.codebase.id, include_main=use_main_slot)
        available_slots: list[WorktreeSlot] = [s for s in all_slots if not s.locked]

        if not available_slots:
            raise AllSlotsLockedException("All worktree slots are currently in use")

        # Strategy 1: Task stickiness - prefer last-used slot
        # Check this FIRST before uncommitted changes check, since task can reuse its own slot regardless
        for slot in available_slots:
            if slot.last_used_by_task_id == task.id:
                # Special handling for main repo slot:
                # Only use it if the task's branch is still checked out there
                if slot.is_main_repo:
                    current_branch = await slot.get_current_branch()
                    if current_branch != task.branch_name:
                        logfire.info(
                            f"Skipping main repo sticky slot {slot.id} for task {task.id}: "
                            f"branch mismatch (current={current_branch}, task={task.branch_name})"
                        )
                        continue
                logfire.info(f"Using sticky slot {slot.id} for task {task.id}")
                return self.worktree_slot_repo.lock_slot(slot, task)

        # Filter out slots with uncommitted changes
        clean_slots = []
        for slot in available_slots:
            has_changes = await self.slot_has_uncommitted_changes(slot)
            if not has_changes:
                clean_slots.append(slot)
            else:
                logfire.info(f"Slot {slot.id} at {slot.path} has uncommitted changes")

        if not clean_slots:
            # All unlocked slots have uncommitted changes
            raise AllSlotsLockedException("All available slots have uncommitted changes")

        available_slots = clean_slots

        # Strategy 2: LRU - least recently used slot
        lru_slot: WorktreeSlot = min(available_slots, key=lambda s: s.last_used_at)
        logfire.info(f"Using LRU slot {lru_slot.id} for task {task.id}")
        return self.worktree_slot_repo.lock_slot(lru_slot, task)

    async def checkout_branch_in_slot(self, slot: WorktreeSlot, branch_name: str) -> bool:
        """Checkout a branch in a slot if it's not already on that branch.

        Args:
            slot: WorktreeSlot to checkout branch in
            branch_name: Name of branch to checkout

        Returns:
            True if checkout was performed, False if already on the branch

        Raises:
            ValueError: If git operations fail
        """
        # Get current branch dynamically
        current_branch = await slot.get_current_branch()

        # Checkout branch if different
        if current_branch != branch_name:
            logfire.info(f"Checking out branch {branch_name} in slot {slot.id}")
            git = GitRepoIntegration(slot.path)
            await git.checkout_branch(branch_name)
            return True

        logfire.info(f"Slot {slot.id} already on branch {branch_name}, skipping checkout")
        return False

    def codebase_slot_count(self, codebase_id: int) -> int:
        slots = self.worktree_slot_repo.get_by_codebase(codebase_id)
        return len(slots)

    def release_slot(self, slot: WorktreeSlot) -> None:
        self.worktree_slot_repo.unlock_slot(slot)
        self.worktree_slot_repo.commit()
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

        # Create slot in database first
        slot = self.worktree_slot_repo.create(
            codebase_id=task.codebase.id,
            path=worktree_path,
            is_main_repo=False,
        )

        # Create the worktree using shared method
        logfire.info(f"Creating worktree at {worktree_path} for task {task.id}")
        await self._create_worktree_for_slot(slot, task)

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
        locked_slots = self.worktree_slot_repo.get_all_locked(codebase_id=codebase_id)
        released_count = 0

        for slot in locked_slots:
            # Check age-based failsafe based on last_used_at
            age = datetime.datetime.now(datetime.UTC) - slot.last_used_at
            if age > datetime.timedelta(hours=1):
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
        existing_main = self.worktree_slot_repo.get_by_path(codebase.local_path)
        if existing_main:
            return existing_main

        # Create main repo slot (current_branch will be determined dynamically)
        logfire.info(f"Bootstrapping main repo slot for codebase {codebase.id}")
        return self.worktree_slot_repo.create(
            codebase_id=codebase.id,
            path=codebase.local_path,
            is_main_repo=True,
        )

    async def delete_worktree_slot(self, slot: WorktreeSlot, force: bool = False) -> None:
        """Delete a worktree slot and associated it worktree

        Args:
            slot: The slot to delete
            force: Force deletion even if locked or has uncommitted changes

        Raises:
            ValueError: If slot not found, is locked (and not forced),
                       is main repo, or git operations fail
        """
        # Cannot delete main repo
        if slot.is_main_repo:
            raise ValueError("Cannot delete main repository slot")

        # Check if locked (unless forced)
        if slot.locked and not force:
            raise ValueError(f"Slot {slot.id} is currently locked")

        codebase = slot.codebase

        # Remove the worktree from git (if it exists)
        if Path(slot.path).exists():
            git = GitRepoIntegration(codebase.local_path)
            try:
                await git.remove_worktree(slot.path, force=force)
                logfire.info(f"Removed worktree at {slot.path}")
            except ShellCommandExecutionError as e:
                error_msg = e.stderr if hasattr(e, "stderr") else str(e)
                raise ValueError(f"Failed to remove worktree at {slot.path}: {error_msg}") from e

        # Delete from database
        self.worktree_slot_repo.delete(slot)
        logfire.info(f"Deleted worktree slot {slot.id}")

    def _check_worktree_valid(self, slot: WorktreeSlot) -> bool:
        """Check if a worktree exists and is valid.

        For worktree slots (non-main repo), checks that the directory exists and contains
        a valid .git file.

        Args:
            slot: The worktree slot to check

        Returns:
            True if worktree is valid, False if missing or invalid
        """
        # Main repo is always valid (it's the source repository)
        if slot.is_main_repo:
            return True

        worktree_path = Path(slot.path)
        git_path = worktree_path / ".git"

        # Check if worktree directory exists and has .git file (worktrees have .git file, not directory)
        return worktree_path.exists() and git_path.exists()

    async def _create_worktree_for_slot(self, slot: WorktreeSlot, task: Task) -> None:
        """Create a worktree for a slot.

        Args:
            slot: The worktree slot to create a worktree for
            task: The task using this slot (for branch information)
        """
        logfire.warn(f"Creating worktree for slot {slot.id} at {slot.path}")
        git = GitRepoIntegration(task.codebase.local_path)
        branch_for_worktree = task.branch_name or task.base_branch
        await git.create_worktree(slot.path, branch_for_worktree)

    async def get_pool_status_for_codebase(self, codebase: Codebase) -> PoolStatus:
        """Get status of all worktree slots for a codebase.

        Args:
            codebase: Codebase instance

        Returns:
            Pool status with codebase info, slot details, and statistics

        Raises:
            ValueError: If codebase not found
        """
        slots = self.worktree_slot_repo.get_by_codebase(codebase.id)

        # Build slot information
        slot_data: list[SlotInfo] = []
        available_count = 0
        locked_count = 0

        for slot in slots:
            if slot.locked:
                locked_count += 1
            else:
                available_count += 1

            # Get current branch dynamically
            current_branch = await slot.get_current_branch()

            # Build locked_by_task info if applicable
            locked_by_task = None
            if slot.locked and slot.last_used_by_task:
                locked_by_task = LockedByTaskInfo(
                    id=slot.last_used_by_task.id,
                    title=slot.last_used_by_task.title,
                    branch=slot.last_used_by_task.branch_name,
                )

            slot_info = SlotInfo(
                id=slot.id,
                path=slot.path,
                is_main_repo=slot.is_main_repo,
                status="locked" if slot.locked else "available",
                current_branch=current_branch,
                last_used_at=slot.last_used_at.isoformat() if slot.last_used_at else None,
                locked_by_task=locked_by_task,
            )

            slot_data.append(slot_info)

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

    async def run_task_agent_in_workspace(
        self,
        task: Task,
        agent_stream: AsyncIterator[ConversationEvent],
        max_worktrees: int | None = None,
        use_main_slot: bool = False,
    ) -> AsyncIterator[ConversationEvent]:
        """Run the task agent in an available workspace slot."""
        slot: WorktreeSlot | None = None
        try:
            # Ensure task has a branch (create if needed, generate name if null)
            # TODO: Make sure task branch already exists by this point so this can be removed
            await self.task_git_service.ensure_task_branch(task)
            # Commit to persist branch_name if it was just generated
            self.task_repo.db.commit()

            # Try to allocate an existing slot
            try:
                slot = await self.allocate_for_task(task, use_main_slot=use_main_slot)
                self.worktree_slot_repo.commit()

                # Emit SystemEvent for workspace allocation
                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_ALLOCATE,
                    data={"task_id": task.id, "slot_id": slot.id},
                    timestamp=datetime.datetime.now(datetime.UTC),
                )

            except AllSlotsLockedException:
                # Check if we've reached the max worktree limit
                if max_worktrees is not None:
                    total_slots = self.codebase_slot_count(task.codebase.id)
                    if total_slots >= max_worktrees:
                        logfire.warn(f"Max worktrees ({max_worktrees}) reached for codebase {task.codebase.id}")
                        raise

                # Create a new slot
                logfire.info(f"All slots locked, creating new worktree for task {task.id}")

                # Emit SystemEvent before creating worktree (this can take time for large repos)
                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_CREATE,
                    data={"task_id": task.id},
                    timestamp=datetime.datetime.now(datetime.UTC),
                )

                slot = await self.create_and_lock_slot(task, use_main_slot=use_main_slot)
                self.worktree_slot_repo.commit()

                # Emit SystemEvent for workspace allocation (creation is a special case of allocation)
                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_ALLOCATE,
                    data={"task_id": task.id, "slot_id": slot.id},
                    timestamp=datetime.datetime.now(datetime.UTC),
                )

            # Verify worktree exists and is valid before checkout (recreate if missing for worktree slots)
            if not self._check_worktree_valid(slot):
                # Emit SystemEvent before creating worktree (this can take time for large repos)
                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_CREATE,
                    data={"task_id": task.id, "slot_id": slot.id},
                    timestamp=datetime.datetime.now(datetime.UTC),
                )
                # Create the worktree
                await self._create_worktree_for_slot(slot, task)

            # Checkout task branch in the allocated slot
            checkout_performed = await self.checkout_branch_in_slot(slot, task.branch_name)

            # Emit SystemEvent for workspace branch checkout only if checkout was performed
            if checkout_performed:
                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_BRANCH_CHECKOUT,
                    data={"task_id": task.id, "branch": task.branch_name},
                    timestamp=datetime.datetime.now(datetime.UTC),
                )

            # Yield the workspace path for use
            logfire.info(f"Allocated workspace {slot.path} for task {task.id}")

            # Run agent conversation in the allocated slot
            async for event in agent_stream:
                yield event

        finally:
            # Always unlock the slot on exit
            if slot:
                self.release_slot(slot)
                logfire.info(f"Released workspace {slot.path} for task {task.id}")


def get_task_workspace_dir(task: Task) -> str:
    """Get the workspace directory for a task, and raise exception if workspace is not allocated"""
    allocated_workspace = task.current_worktree_slot
    if not allocated_workspace:
        raise NoWorktreeAllocatedException("Workspace not allocated for task #{task.id}")
    return allocated_workspace.path
