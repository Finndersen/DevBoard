"""Service for worktree pool management.

Handles worktree pool operations including status queries, slot deletion,
and state reconciliation with actual git worktrees.
"""

from pathlib import Path

import logfire

from devboard.db.repositories.codebase import CodebaseRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import ShellCommandExecutionError


class WorktreePoolService:
    """Service for worktree pool management."""

    def __init__(
        self,
        worktree_slot_repo: WorktreeSlotRepository,
        codebase_repo: CodebaseRepository,
    ):
        """Initialize service.

        Args:
            worktree_slot_repo: Repository for worktree slot operations
            codebase_repo: Repository for codebase operations
        """
        self.worktree_slot_repo = worktree_slot_repo
        self.codebase_repo = codebase_repo

    def get_pool_status(self, codebase_id: int) -> dict:
        """Get status of all worktree slots for a codebase.

        Args:
            codebase_id: ID of the codebase

        Returns:
            Dictionary with pool status information:
            - codebase_id: int
            - codebase_path: str
            - slots: list of slot dictionaries
            - stats: dictionary with total/available/locked counts

        Raises:
            ValueError: If codebase not found
        """
        codebase = self.codebase_repo.get_by_id(codebase_id)
        if not codebase:
            raise ValueError(f"Codebase {codebase_id} not found")

        slots = self.worktree_slot_repo.get_by_codebase(codebase_id)

        # Build slot information
        slot_data = []
        available_count = 0
        locked_count = 0

        for slot in slots:
            if slot.locked:
                locked_count += 1
            else:
                available_count += 1

            # Get current branch dynamically
            current_branch = slot.get_current_branch()

            slot_info = {
                "id": slot.id,
                "path": slot.path,
                "is_main_repo": slot.is_main_repo,
                "status": "locked" if slot.locked else "available",
                "current_branch": current_branch,
                "last_used_at": slot.last_used_at.isoformat() if slot.last_used_at else None,
            }

            if slot.locked and slot.last_used_by_task:
                slot_info["locked_by_task"] = {
                    "id": slot.last_used_by_task.id,
                    "title": slot.last_used_by_task.title,
                    "branch": slot.last_used_by_task.branch_name,
                }

            slot_data.append(slot_info)

        return {
            "codebase_id": codebase_id,
            "codebase_path": codebase.local_path,
            "slots": slot_data,
            "stats": {
                "total_slots": len(slots),
                "available": available_count,
                "locked": locked_count,
            },
        }

    async def delete_worktree_slot(self, slot_id: int, force: bool = False) -> None:
        """Delete a worktree slot.

        Args:
            slot_id: ID of the slot to delete
            force: Force deletion even if locked or has uncommitted changes

        Raises:
            ValueError: If slot not found, is locked (and not forced),
                       is main repo, or git operations fail
        """
        slot = self.worktree_slot_repo.get_by_id(slot_id)
        if not slot:
            raise ValueError(f"Worktree slot {slot_id} not found")

        # Cannot delete main repo
        if slot.is_main_repo:
            raise ValueError("Cannot delete main repository slot")

        # Check if locked (unless forced)
        if slot.locked and not force:
            raise ValueError(f"Slot {slot_id} is currently locked")

        codebase = self.codebase_repo.get_by_id(slot.codebase_id)
        if not codebase:
            raise ValueError(f"Codebase {slot.codebase_id} not found")

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
        logfire.info(f"Deleted worktree slot {slot_id}")

    async def reconcile_state(self, codebase_id: int) -> dict:
        """Reconcile database state with actual git worktrees.

        Syncs DB with git reality by:
        - Removing DB slots for deleted worktrees
        - Discovering manually-created worktrees
        - Releasing all locks (conservative on startup)

        Args:
            codebase_id: ID of the codebase

        Returns:
            Dictionary with reconciliation results:
            - removed_slots: Number of DB slots removed
            - discovered_slots: Number of worktrees discovered
            - released_locks: Number of locks released

        Raises:
            ValueError: If codebase not found or git operations fail
        """
        codebase = self.codebase_repo.get_by_id(codebase_id)
        if not codebase:
            raise ValueError(f"Codebase {codebase_id} not found")

        git = GitRepoIntegration(codebase.local_path)

        # Get actual worktrees from git
        try:
            actual_worktrees = await git.list_worktrees()
        except ShellCommandExecutionError as e:
            error_msg = e.stderr if hasattr(e, "stderr") else str(e)
            raise ValueError(f"Failed to list worktrees: {error_msg}") from e

        # Get DB slots
        db_slots = self.worktree_slot_repo.get_by_codebase(codebase_id)

        removed_count = 0
        discovered_count = 0
        released_locks = 0

        # Cleanup: Remove DB slots for deleted worktrees
        for slot in db_slots:
            if not slot.is_main_repo:
                exists = any(wt.path == slot.path for wt in actual_worktrees)
                if not exists:
                    logfire.info(f"Removing DB slot {slot.id} - worktree no longer exists at {slot.path}")
                    self.worktree_slot_repo.delete(slot)
                    removed_count += 1

        # Discovery: Add DB slots for manually-created worktrees
        for wt in actual_worktrees:
            if self._is_devboard_worktree(wt.path, codebase.local_path):
                exists = any(s.path == wt.path for s in db_slots)
                if not exists:
                    logfire.info(f"Discovered worktree at {wt.path}")
                    self.worktree_slot_repo.create(
                        codebase_id=codebase_id,
                        path=wt.path,
                        is_main_repo=wt.is_main,
                    )
                    discovered_count += 1

        # Cleanup: Release all locks (conservative - safe on restart)
        for slot in db_slots:
            if slot.locked:
                self.worktree_slot_repo.unlock_slot(slot)
                released_locks += 1

        logfire.info(
            f"Reconciled codebase {codebase_id}: "
            f"removed {removed_count} slots, "
            f"discovered {discovered_count} worktrees, "
            f"released {released_locks} locks"
        )

        return {
            "removed_slots": removed_count,
            "discovered_slots": discovered_count,
            "released_locks": released_locks,
        }

    def _is_devboard_worktree(self, worktree_path: str, codebase_path: str) -> bool:
        """Check if a worktree path follows DevBoard naming convention.

        Args:
            worktree_path: Path to the worktree
            codebase_path: Path to the main codebase

        Returns:
            True if worktree follows DevBoard naming convention
        """
        # Main repo is always a DevBoard worktree
        if worktree_path == codebase_path:
            return True

        # Check if worktree follows naming convention: {base_name}.worktree-{n}
        path = Path(worktree_path)
        base_name = Path(codebase_path).name
        name = path.name

        # Pattern: {base_name}.worktree-{number}
        if name.startswith(f"{base_name}.worktree-"):
            suffix = name[len(f"{base_name}.worktree-") :]
            return suffix.isdigit()

        return False
