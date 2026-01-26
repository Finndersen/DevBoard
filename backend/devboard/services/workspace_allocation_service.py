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

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionService
from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType
from devboard.db.models import Codebase, Task, WorktreeSlot
from devboard.db.models.conversation import ParentEntityType
from devboard.db.repositories.conversation import ConversationRepository
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
        conversation_repo: ConversationRepository,
    ):
        """Initialize service.

        Args:
            worktree_slot_repo: Repository for worktree slot operations
            task_repo: Repository for task operations
            conversation_repo: Repository for conversation operations
        """
        self.worktree_slot_repo = worktree_slot_repo
        self.task_repo = task_repo
        self.conversation_repo = conversation_repo
        self.task_git_service = TaskGitService(task_repo=task_repo, worktree_slot_repo=worktree_slot_repo)

    async def slot_has_uncommitted_changes(self, slot: WorktreeSlot) -> bool:
        """Check if a worktree slot has uncommitted git changes."""
        git = GitRepoIntegration(slot.path)
        has_changes = await git.has_uncommitted_changes()
        return has_changes

    async def _migrate_claude_session_if_needed(
        self,
        task: Task,
        new_working_dir: str,
    ) -> None:
        """Migrate Claude Code session if the task has an active Claude Code conversation.

        Automatically finds the session file and migrates it to the new working directory.

        Args:
            task: Task instance
            new_working_dir: The new working directory path
        """
        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task.id)
        if not conversation or conversation.engine != AgentEngine.CLAUDE_CODE:
            return
        if not conversation.external_session_id:
            return

        session_service = ClaudeCodeSessionService()
        try:
            result = await session_service.migrate_session_to_directory(
                session_id=conversation.external_session_id,
                new_working_dir=new_working_dir,
            )
            if result:
                logfire.info(f"Migrated Claude Code session for task {task.id} to {new_working_dir}")
        except FileNotFoundError:
            logfire.debug(f"No Claude Code session file found for task {task.id}, skipping migration")

    async def allocate_for_task(self, task: Task) -> WorktreeSlot:
        """Find an appropriate slot and lock it for a task.

        Implements smart allocation with priority:
        1. Branch location - slot already has task's branch checked out
        2. Task stickiness - prefer last-used slot (with special handling for main repo)
        3. LRU - pick least recently used available slot

        Branch-location strategy prevents git checkout errors when a branch is already
        checked out elsewhere. If the task's branch is checked out in any unlocked slot,
        that slot is used regardless of main repo exclusion rules or uncommitted changes
        (which belong to the task's WIP).

        For main repo slots:
        - When max_worktrees=0: Main repo is included in normal allocation pool
        - When max_worktrees=None or >0: Main repo is excluded from automatic allocation
        - Exception: If task's branch is already checked out in main repo, it's used
        - Main repo slot is only reused for a task via stickiness if the task's branch is still checked out there
        - If main repo has a different branch checked out, the task is allocated a different slot
        - This ensures main repo slot assignment only happens through explicit manual action (unless max_worktrees=0)

        Raises:
            ValueError: If task has invalid configuration
            AllSlotsLockedException: If no suitable slots are available
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch configured")

        # Clean up any stale locks before attempting allocation
        await self.cleanup_stale_locks(codebase_id=task.codebase.id)

        # Determine if main repo should be included in allocation pool
        # When max_worktrees=0, use main repo only mode - include main in pool
        # Otherwise (None or >0), exclude main repo from automatic allocation
        include_main_in_pool = task.codebase.max_worktrees == 0

        # Bootstrap main repo slot if using main-only mode (fallback for existing codebases)
        if include_main_in_pool:
            self.bootstrap_main_repo_slot(task.codebase)

        # Get all slots for this codebase (including main repo for stickiness check)
        all_slots = self.worktree_slot_repo.get_by_codebase(task.codebase.id, include_main=True)

        # Sort slots by last_used_at descending so most recently used is checked first
        # This ensures when multiple slots have the same task ID, we prefer the most recent
        all_slots_sorted = sorted(all_slots, key=lambda s: s.last_used_at, reverse=True)

        # PRIORITY 1: Check if task's branch is already checked out in any available slot
        # This prevents git checkout errors when the branch is checked out elsewhere.
        # Ignores main repo exclusion rules - if branch is there, use it.
        # Ignores uncommitted changes filter - changes are the task's WIP.
        git = GitRepoIntegration(task.codebase.local_path)
        branch_location = await git.get_checked_out_location(task.branch_name)

        if branch_location:
            for slot in all_slots_sorted:
                if slot.path == branch_location and not slot.locked:
                    logfire.info(
                        f"Using slot {slot.id} for task {task.id} - branch {task.branch_name} already checked out there"
                    )
                    return self.worktree_slot_repo.lock_slot(slot, task)

        # PRIORITY 2: Single pass - find sticky slot and build candidate pool simultaneously
        sticky_slot: WorktreeSlot | None = None
        candidate_slots: list[WorktreeSlot] = []

        for slot in all_slots_sorted:
            if slot.locked:
                continue

            # Check for sticky slot (task previously used this slot)
            if slot.last_used_by_task_id == task.id:
                # Main repo requires branch match for stickiness
                if slot.is_main_repo:
                    current_branch = await slot.get_current_branch()
                    if current_branch != task.branch_name:
                        logfire.info(
                            f"Skipping main repo sticky slot {slot.id} for task {task.id}: "
                            f"branch mismatch (current={current_branch}, task={task.branch_name})"
                        )
                    else:
                        sticky_slot = slot
                        break  # Most recent sticky slot found, stop searching
                else:
                    sticky_slot = slot
                    break  # Most recent sticky slot found, stop searching

            # Build candidate pool (respecting main repo inclusion rules)
            if include_main_in_pool or not slot.is_main_repo:
                candidate_slots.append(slot)

        # Use sticky slot immediately if found (skip uncommitted changes check - task owns this slot)
        if sticky_slot:
            logfire.info(f"Using sticky slot {sticky_slot.id} for task {task.id}")
            return self.worktree_slot_repo.lock_slot(sticky_slot, task)

        if not candidate_slots:
            raise AllSlotsLockedException("All worktree slots are currently in use")

        # Filter candidates by uncommitted changes and find LRU in single pass
        # (This pass involves async I/O so must be separate)
        best_slot: WorktreeSlot | None = None
        for slot in candidate_slots:
            if await self.slot_has_uncommitted_changes(slot):
                logfire.info(f"Slot {slot.id} at {slot.path} has uncommitted changes")
                continue
            # Track LRU among clean slots
            if best_slot is None or slot.last_used_at < best_slot.last_used_at:
                best_slot = slot

        if not best_slot:
            raise AllSlotsLockedException("All available slots have uncommitted changes")

        logfire.info(f"Using LRU slot {best_slot.id} for task {task.id}")
        return self.worktree_slot_repo.lock_slot(best_slot, task)

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
        slot_git = GitRepoIntegration(slot.path)
        current_branch = await slot_git.get_current_branch()

        # Checkout branch if different
        if current_branch != branch_name:
            logfire.info(f"Checking out branch {branch_name} in slot {slot.id}")
            await slot_git.checkout_branch(branch_name)
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

    async def create_and_lock_slot(self, task: Task) -> WorktreeSlot:
        """Create a new worktree slot and lock it for a task."""
        # Ensure main repo slot exists before creating worktree slots
        self.bootstrap_main_repo_slot(task.codebase)

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
            # Database returns naive datetimes, so add UTC timezone for comparison
            last_used = slot.last_used_at.replace(tzinfo=datetime.UTC)
            age = datetime.datetime.now(datetime.UTC) - last_used
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

    def _check_can_create_worktree(self, codebase: Codebase) -> bool:
        """Check if a new worktree can be created for the codebase.

        Returns:
            True if a new worktree can be created, False if limit reached
        """
        max_worktrees = codebase.max_worktrees

        # Unlimited worktrees when max_worktrees is None
        if max_worktrees is None:
            return True

        # For max_worktrees=0, we can never create new slots (main repo only)
        if max_worktrees == 0:
            return False

        # For max_worktrees>0, check against the limit (counting worktrees only, not main)
        total_slots = self.codebase_slot_count(codebase.id)
        worktree_count = total_slots - 1 if total_slots > 0 else 0  # subtract main repo slot
        return worktree_count < max_worktrees

    async def run_task_agent_in_workspace(
        self,
        task: Task,
        agent_stream: AsyncIterator[ConversationEvent],
    ) -> AsyncIterator[ConversationEvent]:
        """Run the task agent in an available workspace slot.

        Worktree allocation is controlled by codebase.max_worktrees:
        - None: Unlimited worktrees, main repo excluded from automatic allocation
        - 0: No worktrees, main repo only mode (main repo included in allocation)
        - N (>0): Up to N worktree slots, main repo excluded from automatic allocation
        """
        slot: WorktreeSlot | None = None
        try:
            # Ensure task has a branch (create if needed, generate name if null)
            # TODO: Make sure task branch already exists by this point so this can be removed
            await self.task_git_service.ensure_task_branch(task)
            # Commit to persist branch_name if it was just generated
            self.task_repo.db.commit()

            # Track previous slot to determine if allocation changed
            previous_slot = self.worktree_slot_repo.get_last_used_slot_for_task(task.id)

            # Try to allocate an existing slot
            try:
                slot = await self.allocate_for_task(task)
                self.worktree_slot_repo.commit()

                # Only emit allocation event if slot changed (not sticky reuse)
                if previous_slot is None or slot.id != previous_slot.id:
                    await self._migrate_claude_session_if_needed(
                        task=task,
                        new_working_dir=slot.path,
                    )
                    yield SystemEvent(
                        type=SystemEventType.WORKSPACE_ALLOCATE,
                        data={"task_id": task.id, "slot_id": slot.id},
                        timestamp=datetime.datetime.now(datetime.UTC),
                    )

            except AllSlotsLockedException:
                # Check if we can create a new worktree
                if not self._check_can_create_worktree(task.codebase):
                    logfire.warn(
                        f"Max worktrees ({task.codebase.max_worktrees}) reached for codebase {task.codebase.id}"
                    )
                    yield SystemEvent(
                        type=SystemEventType.STREAM_ERROR,
                        data={
                            "error_code": "SLOTS_EXHAUSTED",
                            "message": "No workspace slots available. Either increase max_worktrees in codebase settings, or wait for an existing task to finish.",
                        },
                        timestamp=datetime.datetime.now(datetime.UTC),
                    )
                    return

                # Create a new slot
                logfire.info(f"All slots locked, creating new worktree for task {task.id}")

                # Emit SystemEvent before creating worktree (this can take time for large repos)
                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_CREATE,
                    data={"task_id": task.id},
                    timestamp=datetime.datetime.now(datetime.UTC),
                )

                slot = await self.create_and_lock_slot(task)
                self.worktree_slot_repo.commit()

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

    async def checkout_task_to_main_repo(self, task: Task) -> None:
        """Checkout a task's branch to the main repository.

        This flow:
        1. Releases the branch from any worktree (stash + detach)
        2. Checks out the task's branch in the main repository
        3. Applies the stashed changes to the main repository
        4. Assigns (but does NOT lock) the main repo slot to the task

        If steps 2 or 3 fail, the worktree is rolled back to its original state.

        Args:
            task: Task instance

        Raises:
            ValueError: If task has no branch name, main repo is dirty, or operation fails
        """
        if not task.branch_name:
            raise ValueError(f"Task {task.id} has no branch name configured")

        main_git = GitRepoIntegration(task.codebase.local_path)

        # Check main repo is clean
        if await main_git.has_uncommitted_changes():
            raise ValueError("Main repository has uncommitted changes")

        # Release branch from worktree if needed (stash + detach)
        release_result = await main_git.release_branch_from_worktree(task.branch_name)

        try:
            # Checkout branch in main repository
            await main_git.checkout_branch(task.branch_name)
            logfire.info(f"Checked out branch {task.branch_name} in main repo for task {task.id}")

            # Apply stashed changes to main repository
            if release_result.stash_sha:
                await main_git.stash_apply(release_result.stash_sha)
                logfire.info(f"Applied stashed changes to main repo for task {task.id}")

        except Exception as e:
            # ROLLBACK: Restore worktree to original state
            if release_result.worktree_path:
                logfire.warning(f"Rolling back worktree state after checkout failure for task {task.id}: {e}")
                worktree_git = GitRepoIntegration(release_result.worktree_path)
                await worktree_git.checkout_branch(task.branch_name)
                if release_result.stash_sha:
                    await worktree_git.stash_apply(release_result.stash_sha)
            raise

        # Migrate Claude Code session to main repo (finds session file automatically)
        await self._migrate_claude_session_if_needed(
            task=task,
            new_working_dir=task.codebase.local_path,
        )

        # Assign (but don't lock) the main repo slot to this task
        main_slot = self.worktree_slot_repo.get_main_slot_for_codebase(task.codebase_id)
        self.worktree_slot_repo.assign_slot(main_slot, task)
        logfire.info(f"Assigned main repo slot to task {task.id}")
