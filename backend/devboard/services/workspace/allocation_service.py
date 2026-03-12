"""WorkspaceAllocationService: orchestrates workspace lifecycle for task agents."""

import datetime
from collections.abc import AsyncIterator
from pathlib import Path

import logfire

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionMigrator
from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType
from devboard.config.integration_configs import WorktreeLocationMode
from devboard.db.models import Codebase, ParentEntityType, Task, WorktreeSlot
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import execute_shell_command
from devboard.services.task_git_service import TaskGitService
from devboard.services.workspace.pool_manager import WorktreePoolManager
from devboard.services.workspace.types import (
    AllSlotsLockedException,
    BranchInUseException,
    SetupCommandError,
)

SETUP_COMMAND_TIMEOUT = 300.0


class WorkspaceAllocationService:
    """Service for workspace allocation and worktree slot management."""

    def __init__(
        self,
        worktree_slot_repo: WorktreeSlotRepository,
        conversation_repo: ConversationRepository,
        worktree_location_mode: WorktreeLocationMode = WorktreeLocationMode.CENTRAL,
    ):
        self.worktree_slot_repo = worktree_slot_repo
        self.conversation_repo = conversation_repo
        self.task_git_service = TaskGitService()
        self._pool_manager = WorktreePoolManager(worktree_slot_repo, worktree_location_mode=worktree_location_mode)

    # Slot utility methods

    async def checkout_branch_in_slot(self, slot: WorktreeSlot, branch_name: str) -> bool:
        """Checkout a branch in a slot if it's not already on that branch.

        Returns:
            True if checkout was performed, False if already on the branch
        """
        slot_git = GitRepoIntegration(slot.path)
        current_branch = await slot_git.get_current_branch()

        if current_branch != branch_name:
            logfire.info(f"Checking out branch {branch_name} in slot {slot.id}")
            await slot_git.checkout_branch(branch_name)
            return True

        logfire.info(f"Slot {slot.id} already on branch {branch_name}, skipping checkout")
        return False

    def _check_worktree_valid(self, slot: WorktreeSlot) -> bool:
        """Check if a worktree exists and is valid."""
        if slot.is_main_repo:
            return True

        worktree_path = Path(slot.path)
        git_path = worktree_path / ".git"
        return worktree_path.exists() and git_path.exists()

    def _check_can_create_worktree(self, codebase: Codebase) -> bool:
        """Check if a new worktree can be created for the codebase."""
        max_worktrees = codebase.max_worktrees

        if max_worktrees is None:
            return True

        if max_worktrees == 0:
            return False

        total_slots = self._pool_manager.codebase_slot_count(codebase.id)
        worktree_count = total_slots - 1 if total_slots > 0 else 0
        return worktree_count < max_worktrees

    async def _migrate_claude_session_if_needed(self, task: Task, new_working_dir: str) -> None:
        """Migrate Claude Code session if the task has an active Claude Code conversation."""
        conversation = self.conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task.id)
        if not conversation or conversation.engine != AgentEngine.CLAUDE_CODE:
            return
        if not conversation.external_session_id:
            return

        migrator = ClaudeCodeSessionMigrator()
        try:
            result = await migrator.migrate_session_to_directory(
                session_id=conversation.external_session_id,
                new_working_dir=new_working_dir,
            )
            if result:
                logfire.info(f"Migrated Claude Code session for task {task.id} to {new_working_dir}")
        except FileNotFoundError:
            logfire.debug(f"No Claude Code session file found for task {task.id}, skipping migration")

    async def _run_setup_command(
        self,
        slot: WorktreeSlot,
        codebase: Codebase,
        task: Task,
    ) -> None:
        """Run the codebase setup command in the worktree slot.

        Raises:
            SetupCommandError: If the setup command fails
        """
        if not codebase.setup_command:
            return

        logfire.info(f"Running setup command for task {task.id} in {slot.path}: {codebase.setup_command}")

        result = await execute_shell_command(
            command=["bash", "-c", codebase.setup_command],
            working_dir=slot.path,
            timeout=SETUP_COMMAND_TIMEOUT,
            raise_on_error=False,
        )

        if not result.success:
            error_output = result.stderr.strip() or result.stdout.strip() or "Setup command failed"
            logfire.error(f"Setup command failed for task {task.id} (exit code {result.returncode}): {error_output}")
            raise SetupCommandError(
                message=error_output,
                command=codebase.setup_command,
                returncode=result.returncode,
            )

        logfire.info(f"Setup command completed successfully for task {task.id}")

    def _release_workspace(self, task: Task, slot: WorktreeSlot | None) -> None:
        """Release a locked workspace slot."""
        if slot:
            self._pool_manager.release_slot(slot)
            logfire.info(f"Released workspace {slot.path} for task {task.id}")

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
            # Ensure git branch exists (create if needed)
            await self.task_git_service.ensure_task_branch(task)

            # Track previous slot to determine if allocation changed
            previous_slot = task.last_used_worktree_slot

            # Try to allocate an existing slot
            try:
                slot = await self._pool_manager.allocate_for_task(task)
                self.worktree_slot_repo.commit()

                if previous_slot is None or slot.id != previous_slot.id:
                    yield SystemEvent(
                        type=SystemEventType.WORKSPACE_ALLOCATE,
                        data={"task_id": task.id, "slot_id": slot.id},
                        timestamp=datetime.datetime.now(datetime.UTC),
                    )

            except BranchInUseException as e:
                yield SystemEvent(
                    type=SystemEventType.STREAM_ERROR,
                    data={
                        "error_code": "BRANCH_IN_USE",
                        "message": str(e),
                    },
                    timestamp=datetime.datetime.now(datetime.UTC),
                )
                return

            except AllSlotsLockedException:
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

                logfire.info(f"All slots locked, creating new worktree for task {task.id}")

                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_CREATE,
                    data={"task_id": task.id},
                    timestamp=datetime.datetime.now(datetime.UTC),
                )

                slot = await self._pool_manager.create_and_lock_slot(task)
                self.worktree_slot_repo.commit()

            # Verify worktree exists and is valid (recreate if missing)
            if not self._check_worktree_valid(slot):
                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_CREATE,
                    data={"task_id": task.id, "slot_id": slot.id},
                    timestamp=datetime.datetime.now(datetime.UTC),
                )
                await self._pool_manager._create_worktree_for_slot(slot, task)

            # Checkout task branch in the allocated slot
            checkout_performed = await self.checkout_branch_in_slot(slot, task.branch_name)

            if checkout_performed:
                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_BRANCH_CHECKOUT,
                    data={"task_id": task.id, "branch": task.branch_name},
                    timestamp=datetime.datetime.now(datetime.UTC),
                )

            # Run setup command if configured and checkout was performed
            if checkout_performed and task.codebase.setup_command:
                yield SystemEvent(
                    type=SystemEventType.WORKSPACE_SETUP,
                    data={
                        "task_id": task.id,
                        "codebase_id": task.codebase.id,
                        "setup_command": task.codebase.setup_command,
                    },
                    timestamp=datetime.datetime.now(datetime.UTC),
                )

                try:
                    await self._run_setup_command(slot, task.codebase, task)
                except SetupCommandError as e:
                    yield SystemEvent(
                        type=SystemEventType.STREAM_ERROR,
                        data={
                            "error_code": "SETUP_COMMAND_FAILED",
                            "message": f"Workspace setup command failed: {e.message}",
                        },
                        timestamp=datetime.datetime.now(datetime.UTC),
                    )
                    return

            logfire.info(f"Allocated workspace {slot.path} for task {task.id}")

            # Always verify session is in the correct location before streaming (no-op if already correct)
            await self._migrate_claude_session_if_needed(task=task, new_working_dir=slot.path)

            async for event in agent_stream:
                yield event

        finally:
            self._release_workspace(task, slot)

    async def checkout_task_to_main_repo(self, task: Task) -> None:
        """Checkout a task's branch to the main repository.

        This flow:
        1. Releases the branch from any worktree (stash + detach)
        2. Checks out the task's branch in the main repository
        3. Applies the stashed changes to the main repository
        4. Assigns (but does NOT lock) the main repo slot to the task

        Raises:
            ValueError: If main repo is dirty or operation fails
        """
        main_git = GitRepoIntegration(task.codebase.local_path)

        if await main_git.has_uncommitted_changes():
            raise ValueError("Main repository has uncommitted changes")

        release_result = await main_git.release_branch_from_worktree(task.branch_name)

        try:
            await main_git.checkout_branch(task.branch_name)
            logfire.info(f"Checked out branch {task.branch_name} in main repo for task {task.id}")

            if release_result.stash_sha:
                await main_git.stash_apply(release_result.stash_sha)
                logfire.info(f"Applied stashed changes to main repo for task {task.id}")

        except Exception as e:
            if release_result.worktree_path:
                logfire.warning(f"Rolling back worktree state after checkout failure for task {task.id}: {e}")
                worktree_git = GitRepoIntegration(release_result.worktree_path)
                await worktree_git.checkout_branch(task.branch_name)
                if release_result.stash_sha:
                    await worktree_git.stash_apply(release_result.stash_sha)
            raise

        await self._migrate_claude_session_if_needed(
            task=task,
            new_working_dir=task.codebase.local_path,
        )

        main_slot = self.worktree_slot_repo.get_main_slot_for_codebase(task.codebase_id)
        self.worktree_slot_repo.assign_slot(main_slot, task)
        logfire.info(f"Assigned main repo slot to task {task.id}")
