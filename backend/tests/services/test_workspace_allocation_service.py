"""Tests for WorkspaceService."""

import datetime
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.events import SystemEvent, SystemEventType
from devboard.db.models import Codebase, Task, WorktreeSlot
from devboard.services.task_git_service import TaskGitService
from devboard.services.workspace import (
    AllSlotsLockedException,
    BranchInUseException,
    WorkspaceService,
)
from devboard.services.workspace.types import AllocationResult


@pytest.fixture
def mock_repos():
    """Create mock repositories."""
    worktree_slot_repo = MagicMock()
    task_repo = MagicMock()
    task_repo.db = MagicMock()  # Mock db for commit() calls
    conversation_repo = MagicMock()
    return worktree_slot_repo, task_repo, conversation_repo


@pytest.fixture
def service(mock_repos):
    """Create service instance with mocked repos."""
    worktree_slot_repo, _, conversation_repo = mock_repos
    return WorkspaceService(
        worktree_slot_repo=worktree_slot_repo,
        conversation_repo=conversation_repo,
    )


@pytest.fixture(autouse=True)
def patch_verify_task_branch_exists():
    """Patch TaskGitService.verify_task_branch_exists to avoid git operations in tests."""
    with patch(
        "devboard.services.workspace.workspace_service.TaskGitService.verify_task_branch_exists",
        new_callable=AsyncMock,
    ) as mock_verify:
        mock_verify.return_value = None
        yield mock_verify


@pytest.fixture
def sample_codebase():
    """Create a sample codebase."""
    codebase = MagicMock(spec=Codebase)
    codebase.id = 1
    codebase.local_path = "/projects/test-repo"
    codebase.name = "Test Repo"
    codebase.max_worktrees = None  # Default: unlimited worktrees
    codebase.setup_command = None  # No setup command by default
    return codebase


@pytest.fixture
def sample_task(sample_codebase):
    """Create a sample task."""
    task = MagicMock(spec=Task)
    task.id = 1
    task.branch_name = "feature/test-branch"
    task.base_branch = "main"
    task.codebase_id = 1
    task.codebase = sample_codebase
    task.title = "Test Task"
    return task


@pytest.fixture
def sample_slot():
    """Create a sample worktree slot (non-main repo)."""
    slot = MagicMock(spec=WorktreeSlot)
    slot.id = 1
    slot.path = "/projects/test-repo.worktree-1"
    slot.is_main_repo = False
    slot.locked_by_task_id = None
    slot.last_used_by_task_id = None
    slot.last_used_at = datetime.datetime.now(datetime.UTC)
    slot.get_current_branch = AsyncMock(return_value="main")
    return slot


# =============================================================================
# Branch-Location Allocation Strategy Tests
# =============================================================================


@pytest.mark.asyncio
async def test_allocate_for_task_branch_already_checked_out_in_worktree(
    service, mock_repos, sample_task, sample_codebase, sample_slot
):
    """Test that allocation uses slot where branch is already checked out."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Branch is checked out in a worktree slot
    sample_slot.locked = False
    sample_slot.last_used_by_task_id = 999  # Different task
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=sample_slot.path)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Used slot where branch was checked out (not stickiness or LRU)
    assert result == AllocationResult(slot=sample_slot, reused=True)
    worktree_slot_repo.lock_slot.assert_called_once_with(sample_slot, sample_task)
    # Verify get_checked_out_location was called for branch-location check
    mock_git.return_value.get_checked_out_location.assert_called_once_with(sample_task.branch_name)


@pytest.mark.asyncio
async def test_allocate_for_task_branch_in_main_repo_ignores_exclusion(
    service, mock_repos, sample_task, sample_codebase
):
    """Test that branch-location strategy uses main repo even when excluded from pool."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: max_worktrees > 0 (main repo excluded from automatic allocation)
    sample_codebase.max_worktrees = 2
    sample_task.codebase = sample_codebase

    # Setup: Main repo slot with branch already checked out
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.id = 1
    main_slot.path = sample_codebase.local_path
    main_slot.is_main_repo = True
    main_slot.locked = False
    main_slot.last_used_by_task_id = 999  # Different task
    main_slot.last_used_at = datetime.datetime.now(datetime.UTC)

    worktree_slot_repo.get_by_codebase.return_value = [main_slot]
    worktree_slot_repo.lock_slot.return_value = main_slot

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        # Branch is checked out in main repo
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=sample_codebase.local_path)

        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Main repo was used despite exclusion (branch is there)
    assert result == AllocationResult(slot=main_slot, reused=True)
    worktree_slot_repo.lock_slot.assert_called_once_with(main_slot, sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_branch_location_with_uncommitted_changes(
    service, mock_repos, sample_task, sample_codebase, sample_slot
):
    """Test that branch-location strategy ignores uncommitted changes (task's WIP)."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Slot with uncommitted changes
    sample_slot.locked = False
    sample_slot.last_used_by_task_id = 999  # Different task
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        # Branch is checked out in slot with uncommitted changes
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=sample_slot.path)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=True)

        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Slot was used despite uncommitted changes
    assert result == AllocationResult(slot=sample_slot, reused=True)
    worktree_slot_repo.lock_slot.assert_called_once_with(sample_slot, sample_task)
    # Verify has_uncommitted_changes was NOT called (branch-location skips this check)
    mock_git.return_value.has_uncommitted_changes.assert_not_called()


@pytest.mark.asyncio
async def test_allocate_for_task_branch_location_slot_locked_raises_exception(
    service, mock_repos, sample_task, sample_codebase, sample_slot
):
    """Test that if branch's slot is locked, allocation raises BranchInUseException."""
    worktree_slot_repo, task_repo, _ = mock_repos

    now = datetime.datetime.now(datetime.UTC)

    # Setup: Slot with branch is locked
    branch_slot = MagicMock(spec=WorktreeSlot)
    branch_slot.id = 1
    branch_slot.path = "/projects/test-repo.worktree-1"
    branch_slot.is_main_repo = False
    branch_slot.locked = True  # Locked!
    branch_slot.last_used_by_task_id = 999
    branch_slot.last_used_at = now - timedelta(hours=1)

    # Setup: Another slot available for LRU (but should not be used because branch is in locked slot)
    sample_slot.id = 2
    sample_slot.path = "/projects/test-repo.worktree-2"  # Different path than branch_slot
    sample_slot.locked = False
    sample_slot.last_used_by_task_id = None
    sample_slot.last_used_at = now

    worktree_slot_repo.get_by_codebase.return_value = [branch_slot, sample_slot]

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        # Branch is checked out in locked slot
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=branch_slot.path)

        with pytest.raises(BranchInUseException) as exc_info:
            await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Exception message contains branch name and task id
    assert sample_task.branch_name in str(exc_info.value)
    assert "999" in str(exc_info.value)
    # Verify: No slot was locked (allocation failed)
    worktree_slot_repo.lock_slot.assert_not_called()


@pytest.mark.asyncio
async def test_allocate_for_task_no_branch_name_raises_error(
    service, mock_repos, sample_task, sample_codebase, sample_slot
):
    """Test that allocation raises ValueError when task has no branch_name."""
    # Setup: Task has no branch name
    sample_task.branch_name = None

    with pytest.raises(ValueError, match="has no branch configured"):
        await service._pool_manager.allocate_for_task(sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_branch_not_checked_out_anywhere(
    service, mock_repos, sample_task, sample_codebase, sample_slot
):
    """Test that allocation falls back to stickiness/LRU when branch isn't checked out."""
    worktree_slot_repo, task_repo, _ = mock_repos

    sample_slot.locked = False
    sample_slot.last_used_by_task_id = None
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        # Branch is not checked out anywhere
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Fell back to LRU (branch not checked out)
    assert result == AllocationResult(slot=sample_slot, reused=False)
    worktree_slot_repo.lock_slot.assert_called_once_with(sample_slot, sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_branch_location_takes_priority_over_stickiness(
    service, mock_repos, sample_task, sample_codebase
):
    """Test that branch-location takes priority over sticky slot."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Sticky slot (different from where branch is checked out)
    sticky_slot = MagicMock(spec=WorktreeSlot)
    sticky_slot.id = 1
    sticky_slot.path = "/projects/test-repo.worktree-1"
    sticky_slot.is_main_repo = False
    sticky_slot.locked = False
    sticky_slot.last_used_by_task_id = sample_task.id  # Sticky slot for this task
    sticky_slot.last_used_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)

    # Setup: Slot where branch is currently checked out
    branch_slot = MagicMock(spec=WorktreeSlot)
    branch_slot.id = 2
    branch_slot.path = "/projects/test-repo.worktree-2"
    branch_slot.is_main_repo = False
    branch_slot.locked = False
    branch_slot.last_used_by_task_id = 999  # Different task
    branch_slot.last_used_at = datetime.datetime.now(datetime.UTC)

    worktree_slot_repo.get_by_codebase.return_value = [sticky_slot, branch_slot]
    worktree_slot_repo.lock_slot.return_value = branch_slot

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        # Branch is checked out in branch_slot, not sticky_slot
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=branch_slot.path)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Used branch_slot (where branch is) instead of sticky_slot
    assert result == AllocationResult(slot=branch_slot, reused=True)
    worktree_slot_repo.lock_slot.assert_called_once_with(branch_slot, sample_task)


# =============================================================================
# Task Stickiness Allocation Strategy Tests
# =============================================================================


@pytest.mark.asyncio
async def test_allocate_for_task_sticky_slot(service, mock_repos, sample_task, sample_codebase, sample_slot):
    """Test allocation with task stickiness (prefer previously used slot)."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Task previously used this slot
    sample_slot.last_used_by_task_id = sample_task.id
    sample_slot.locked = False  # Available
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot  # Return same slot after locking
    # Mock git dirty check (clean slot)
    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        # Branch not checked out anywhere (falls through to stickiness)
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute (no branch checkout - that's caller's responsibility)
        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Returned the sticky slot
    assert result == AllocationResult(slot=sample_slot, reused=True)
    worktree_slot_repo.lock_slot.assert_called_once_with(sample_slot, sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_branch_optimization(service, mock_repos, sample_task, sample_codebase, sample_slot):
    """Test allocation with branch optimization (slot already on base branch)."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: No sticky slot, but slot already on base branch
    sample_slot.locked = False  # Available
    sample_slot.last_used_by_task_id = 99  # Not this task
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot  # Return same slot after locking
    # Mock the slot's current branch to match task's base branch
    sample_slot.get_current_branch.return_value = sample_task.base_branch

    # Mock git dirty check (clean slot)
    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        # Branch not checked out anywhere (falls through to LRU)
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute - should use branch optimization
        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Used branch optimization
    assert result == AllocationResult(slot=sample_slot, reused=False)
    worktree_slot_repo.lock_slot.assert_called_once_with(sample_slot, sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_all_slots_locked(service, mock_repos, sample_task, sample_codebase):
    """Test allocation when all slots are locked."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: All slots are locked (empty available_slots)
    locked_slot = MagicMock(spec=WorktreeSlot)
    locked_slot.locked = True
    locked_slot.last_used_by_task = MagicMock()
    locked_slot.last_used_by_task.id = 2
    locked_slot.last_used_by_task.title = "Other Task"
    locked_slot.path = "/projects/test-repo"

    worktree_slot_repo.get_by_codebase.return_value = [locked_slot]  # Only locked slots

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        # Branch location check finds nothing (slot is locked anyway)
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)

        # Execute and verify exception
        with pytest.raises(AllSlotsLockedException):
            await service._pool_manager.allocate_for_task(sample_task)


@pytest.mark.asyncio
async def test_cleanup_stale_locks(service, mock_repos, sample_codebase):
    """Test cleanup of stale locks based on last_used_at age."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Locked slot from 45 minutes ago (older than 30min threshold)
    locked_slot = MagicMock(spec=WorktreeSlot)
    locked_slot.id = 1
    locked_slot.last_used_by_task_id = 1
    locked_slot.last_used_at = datetime.datetime.now(datetime.UTC) - timedelta(minutes=45)

    worktree_slot_repo.get_all_locked.return_value = [locked_slot]

    # Execute
    released_count = await service._pool_manager.cleanup_stale_locks(sample_codebase.id)

    # Verify: Lock was released (>30min age threshold)
    assert released_count == 1
    worktree_slot_repo.unlock_slot.assert_called_once_with(locked_slot)


@pytest.mark.asyncio
async def test_cleanup_stale_locks_does_not_release_recent(service, mock_repos, sample_codebase):
    """Test that locks within the 30min threshold are not released."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Recently locked slot (15 minutes ago, within 30min threshold)
    recent_slot = MagicMock(spec=WorktreeSlot)
    recent_slot.id = 1
    recent_slot.last_used_by_task_id = 1
    recent_slot.last_used_at = datetime.datetime.now(datetime.UTC) - timedelta(minutes=15)

    worktree_slot_repo.get_all_locked.return_value = [recent_slot]

    # Execute
    released_count = await service._pool_manager.cleanup_stale_locks(sample_codebase.id)

    # Verify: Lock was NOT released (within 30min threshold)
    assert released_count == 0
    worktree_slot_repo.unlock_slot.assert_not_called()


def test_bootstrap_main_repo_slot(service, mock_repos, sample_codebase):
    """Test bootstrapping main repo slot when none exists."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: No existing slots
    worktree_slot_repo.find_one.return_value = None  # No slot found
    worktree_slot_repo.get_by_path.return_value = None  # No slot at main repo path

    # Mock slot creation
    new_slot = MagicMock(spec=WorktreeSlot)
    new_slot.id = 1
    new_slot.path = sample_codebase.local_path
    new_slot.is_main_repo = True
    worktree_slot_repo.create.return_value = new_slot

    # Execute (not async)
    service._pool_manager.bootstrap_main_repo_slot(sample_codebase)

    # Verify: Created main repo slot
    worktree_slot_repo.create.assert_called_once()


def test_release_slot(service, mock_repos):
    """Test releasing a slot."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Mock slot
    slot = MagicMock(spec=WorktreeSlot)
    slot.id = 1

    # Execute (not async) - now takes WorktreeSlot instance
    service._pool_manager.release_slot(slot)

    # Verify: Unlocked the slot
    worktree_slot_repo.unlock_slot.assert_called_once_with(slot)


@pytest.mark.asyncio
async def test_prepare_workspace_migration_always_called(service, mock_repos, sample_task, sample_slot):
    """Test that session migration is always attempted during workspace preparation."""
    _, _, conversation_repo = mock_repos

    # Setup: Active Claude Code conversation with session
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.CLAUDE_CODE
    mock_conversation.external_session_id = "test-session-id"
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with (
        patch.object(service, "_check_worktree_valid", return_value=True),
        patch.object(service, "checkout_branch_in_slot", new_callable=AsyncMock, return_value=False),
        patch("devboard.services.workspace.workspace_service.ClaudeCodeSessionMigrator") as mock_migrator_class,
    ):
        mock_migrator = AsyncMock()
        mock_migrator.migrate_session_to_directory = AsyncMock(return_value=None)
        mock_migrator_class.return_value = mock_migrator

        events = []
        async for event in service.prepare_workspace(task=sample_task, slot=sample_slot):
            events.append(event)

    mock_migrator.migrate_session_to_directory.assert_called_once_with(
        session_id="test-session-id",
        new_working_dir=sample_slot.path,
    )


@pytest.mark.asyncio
async def test_allocate_for_task_bootstraps_main_repo_when_max_worktrees_zero(
    service, mock_repos, sample_task, sample_codebase
):
    """Test that allocate_for_task bootstraps main repo slot when max_worktrees=0."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: max_worktrees=0 (main repo only mode)
    sample_codebase.max_worktrees = 0
    sample_task.codebase = sample_codebase

    # Setup: No existing slots initially
    worktree_slot_repo.get_by_path.return_value = None

    # Setup: Mock bootstrap to create main repo slot
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.id = 1
    main_slot.path = sample_codebase.local_path
    main_slot.is_main_repo = True
    main_slot.locked = False
    main_slot.last_used_by_task_id = None
    main_slot.last_used_at = datetime.datetime.now(datetime.UTC)
    main_slot.get_current_branch = AsyncMock(return_value="main")
    worktree_slot_repo.create.return_value = main_slot

    # After bootstrap, get_by_codebase returns the main slot
    worktree_slot_repo.get_by_codebase.return_value = [main_slot]
    worktree_slot_repo.lock_slot.return_value = main_slot

    # Mock git operations
    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute
        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: bootstrap_main_repo_slot was called (via create)
    worktree_slot_repo.create.assert_called_once()
    call_kwargs = worktree_slot_repo.create.call_args[1]
    assert call_kwargs["is_main_repo"] is True
    assert call_kwargs["path"] == sample_codebase.local_path

    # Verify: Main slot was locked
    worktree_slot_repo.lock_slot.assert_called_once_with(main_slot, sample_task)
    assert result == AllocationResult(slot=main_slot, reused=False)


# =============================================================================
# allocate_workspace context manager tests
# =============================================================================


@pytest.mark.asyncio
async def test_allocate_workspace_yields_slot_and_releases(service, mock_repos, sample_task, sample_slot):
    """Test that allocate_workspace yields a locked slot and releases it on exit."""
    worktree_slot_repo, _, _ = mock_repos

    sample_slot.locked = False
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        async with service.allocate_workspace(sample_task) as allocation:
            assert allocation == AllocationResult(slot=sample_slot, reused=False)

    worktree_slot_repo.unlock_slot.assert_called_once_with(sample_slot)


@pytest.mark.asyncio
async def test_allocate_workspace_raises_branch_in_use(service, mock_repos, sample_task, sample_slot):
    """Test that allocate_workspace raises BranchInUseException."""
    worktree_slot_repo, _, _ = mock_repos

    sample_slot.locked = True
    sample_slot.last_used_by_task_id = 999
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=sample_slot.path)

        with pytest.raises(BranchInUseException):
            async with service.allocate_workspace(sample_task):
                pass

    worktree_slot_repo.unlock_slot.assert_not_called()


@pytest.mark.asyncio
async def test_allocate_workspace_raises_all_slots_locked(service, mock_repos, sample_task, sample_codebase):
    """Test that allocate_workspace raises AllSlotsLockedException when max slots reached."""
    worktree_slot_repo, _, _ = mock_repos

    sample_codebase.max_worktrees = 0
    sample_task.codebase = sample_codebase

    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.locked = True
    main_slot.last_used_by_task_id = 999
    main_slot.is_main_repo = True
    main_slot.path = sample_codebase.local_path
    worktree_slot_repo.get_by_codebase.return_value = [main_slot]
    worktree_slot_repo.get_by_path.return_value = main_slot

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        with pytest.raises(AllSlotsLockedException):
            async with service.allocate_workspace(sample_task):
                pass


@pytest.mark.asyncio
async def test_allocate_workspace_creates_new_slot_when_all_locked(service, mock_repos, sample_task, sample_codebase):
    """Test that allocate_workspace creates a new slot when all existing slots are locked."""
    worktree_slot_repo, _, _ = mock_repos

    sample_codebase.max_worktrees = None  # Unlimited
    sample_task.codebase = sample_codebase

    locked_slot = MagicMock(spec=WorktreeSlot)
    locked_slot.locked = True
    locked_slot.is_main_repo = False
    worktree_slot_repo.get_by_codebase.return_value = [locked_slot]

    new_slot = MagicMock(spec=WorktreeSlot)
    new_slot.id = 2
    new_slot.path = "/projects/test-repo.worktree-1"
    new_slot.is_main_repo = False
    worktree_slot_repo.create.return_value = new_slot
    worktree_slot_repo.lock_slot.return_value = new_slot
    worktree_slot_repo.get_by_path.return_value = MagicMock()

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)

        async with service.allocate_workspace(sample_task) as allocation:
            assert allocation == AllocationResult(slot=new_slot, reused=False)

    worktree_slot_repo.unlock_slot.assert_called_once_with(new_slot)


# =============================================================================
# prepare_workspace tests
# =============================================================================


@pytest.mark.asyncio
async def test_prepare_workspace_creates_worktree_if_invalid(service, sample_task, sample_slot):
    """Test that prepare_workspace creates worktree when slot is invalid."""
    with (
        patch.object(service, "_check_worktree_valid", return_value=False),
        patch("devboard.services.workspace.workspace_service.GitRepoIntegration", return_value=AsyncMock()),
        patch.object(service._pool_manager, "create_worktree_for_slot", new_callable=AsyncMock) as mock_create,
        patch.object(service, "checkout_branch_in_slot", new_callable=AsyncMock, return_value=False),
        patch.object(service, "_migrate_claude_session_if_needed", new_callable=AsyncMock),
    ):

        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        events = []
        async for event in service.prepare_workspace(task=sample_task, slot=sample_slot):
            events.append(event)

    system_events = [e for e in events if isinstance(e, SystemEvent)]
    assert len(system_events) == 1
    assert system_events[0].type == SystemEventType.WORKSPACE_CREATE
    mock_create.assert_called_once_with(sample_slot, sample_task)


@pytest.mark.asyncio
async def test_prepare_workspace_skips_worktree_creation_if_valid(service, sample_task, sample_slot):
    """Test that prepare_workspace skips worktree creation when slot is valid."""
    with (
        patch.object(service, "_check_worktree_valid", return_value=True),
        patch.object(service._pool_manager, "create_worktree_for_slot", new_callable=AsyncMock) as mock_create,
        patch.object(service, "checkout_branch_in_slot", new_callable=AsyncMock, return_value=False),
        patch.object(service, "_migrate_claude_session_if_needed", new_callable=AsyncMock),
    ):

        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        events = []
        async for event in service.prepare_workspace(task=sample_task, slot=sample_slot):
            events.append(event)

    system_events = [e for e in events if isinstance(e, SystemEvent)]
    assert len(system_events) == 0
    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_prepare_workspace_runs_setup_after_checkout(service, sample_task, sample_slot):
    """Test that setup command runs when checkout is performed and setup_command is configured."""
    sample_task.codebase.setup_command = "npm install"

    with (
        patch.object(service, "_check_worktree_valid", return_value=True),
        patch.object(service, "checkout_branch_in_slot", new_callable=AsyncMock, return_value=True),
        patch.object(service, "_run_setup_command", new_callable=AsyncMock) as mock_setup,
        patch.object(service, "_migrate_claude_session_if_needed", new_callable=AsyncMock),
    ):

        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        events = []
        async for event in service.prepare_workspace(task=sample_task, slot=sample_slot):
            events.append(event)

    system_events = [e for e in events if isinstance(e, SystemEvent)]
    event_types = [e.type for e in system_events]
    assert SystemEventType.WORKSPACE_BRANCH_CHECKOUT in event_types
    assert SystemEventType.WORKSPACE_SETUP in event_types
    mock_setup.assert_called_once_with(sample_slot, sample_task.codebase, sample_task)


@pytest.mark.asyncio
async def test_prepare_workspace_runs_setup_after_worktree_creation(service, sample_task, sample_slot):
    """Test that setup command runs after fresh worktree creation even without branch checkout."""
    sample_task.codebase.setup_command = "npm install"

    with (
        patch.object(service, "_check_worktree_valid", return_value=False),
        patch("devboard.services.workspace.workspace_service.GitRepoIntegration", return_value=AsyncMock()),
        patch.object(service._pool_manager, "create_worktree_for_slot", new_callable=AsyncMock),
        patch.object(service, "checkout_branch_in_slot", new_callable=AsyncMock, return_value=False),
        patch.object(service, "_run_setup_command", new_callable=AsyncMock) as mock_setup,
        patch.object(service, "_migrate_claude_session_if_needed", new_callable=AsyncMock),
    ):

        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        events = []
        async for event in service.prepare_workspace(task=sample_task, slot=sample_slot):
            events.append(event)

    system_events = [e for e in events if isinstance(e, SystemEvent)]
    event_types = [e.type for e in system_events]
    assert SystemEventType.WORKSPACE_CREATE in event_types
    assert SystemEventType.WORKSPACE_SETUP in event_types
    mock_setup.assert_called_once_with(sample_slot, sample_task.codebase, sample_task)


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_stashes_uncommitted_changes(service, mock_repos, sample_task, sample_slot):
    """Test that uncommitted changes from worktree are applied to main repo."""
    worktree_slot_repo, _, _ = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    with patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_class:
        main_git = AsyncMock()
        mock_git_class.return_value = main_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree - returns stash SHA from worktree
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path="/projects/test-repo.worktree-1",
            stash_sha="abc123stashsha",
        )

        # Execute
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: release_branch_from_worktree was called
        main_git.release_branch_from_worktree.assert_called_once_with(sample_task.branch_name)

        # Verify: Branch checked out in main repo
        main_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: Stash applied in main repo
        main_git.stash_apply.assert_called_once_with("abc123stashsha")

        # Verify: Slot is assigned (not locked) to the task
        worktree_slot_repo.assign_slot.assert_called_once_with(main_slot, sample_task)
        worktree_slot_repo.lock_slot.assert_not_called()


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_no_stash_when_no_changes(service, mock_repos, sample_task, sample_slot):
    """Test that no stash is applied when worktree has no uncommitted changes."""
    worktree_slot_repo, _, _ = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    with patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_class:
        main_git = AsyncMock()
        mock_git_class.return_value = main_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree - no stash SHA (no uncommitted changes)
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path="/projects/test-repo.worktree-1",
            stash_sha=None,  # No uncommitted changes
        )

        # Execute
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: No stash applied (stash_sha was None)
        main_git.stash_apply.assert_not_called()

        # Verify: Branch still checked out
        main_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: Slot is assigned (not locked) to the task
        worktree_slot_repo.assign_slot.assert_called_once_with(main_slot, sample_task)
        worktree_slot_repo.lock_slot.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_task_branch_with_uncommitted_changes(mock_repos, sample_task, sample_slot):
    """Test rebase_task_branch stashes changes, rebases, and restores stash."""
    from devboard.services.task_git_service import RebaseOutcome, RebaseResult

    worktree_slot_repo, _, _ = mock_repos

    # Setup: Task has a worktree slot
    sample_task.last_used_worktree_slot = sample_slot

    with patch("devboard.services.task_git.rebase_coordinator.GitRepoIntegration") as mock_git_class:
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git

        # is_rebase_in_progress is sync, must be a regular Mock
        mock_git.is_rebase_in_progress = Mock(return_value=False)
        # stash_push returns a ref (changes were stashed)
        mock_git.stash_push.return_value = "abc1234"
        mock_git.rebase_branch.return_value = "newhead456"
        # find_stash_by_message returns stash ref after stash_push, then None after drop
        mock_git.find_stash_by_message.side_effect = ["stash@{0}", None]

        # Execute
        result = await TaskGitService.rebase_task_branch(sample_task)

        # Verify result
        assert isinstance(result, RebaseResult)
        assert result.outcome == RebaseOutcome.SUCCESS
        assert result.new_head == "newhead456"
        assert result.slot_path == sample_slot.path
        assert result.has_pending_stash is False

        # Verify stash flow: stash_push always called, has_uncommitted_changes never called
        mock_git.has_uncommitted_changes.assert_not_called()
        mock_git.stash_push.assert_called_once()
        mock_git.rebase_branch.assert_called_once_with(
            sample_task.branch_name, sample_task.base_branch, abort_on_conflict=False
        )
        mock_git.stash_apply.assert_called_once_with("stash@{0}")
        mock_git.stash_drop.assert_called_once_with("stash@{0}")


@pytest.mark.asyncio
async def test_rebase_task_branch_without_uncommitted_changes(mock_repos, sample_task, sample_slot):
    """Test rebase_task_branch with nothing to stash skips stash apply/drop."""
    from devboard.services.task_git_service import RebaseOutcome, RebaseResult

    worktree_slot_repo, _, _ = mock_repos
    sample_task.last_used_worktree_slot = sample_slot

    with patch("devboard.services.task_git.rebase_coordinator.GitRepoIntegration") as mock_git_class:
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git

        # is_rebase_in_progress is sync, must be a regular Mock
        mock_git.is_rebase_in_progress = Mock(return_value=False)
        # stash_push returns None (nothing was stashed)
        mock_git.stash_push.return_value = None
        mock_git.rebase_branch.return_value = "newhead789"
        # No stash exists
        mock_git.find_stash_by_message.return_value = None

        # Execute
        result = await TaskGitService.rebase_task_branch(sample_task)

        # Verify result
        assert isinstance(result, RebaseResult)
        assert result.outcome == RebaseOutcome.SUCCESS
        assert result.new_head == "newhead789"
        assert result.has_pending_stash is False

        # stash_push always called; no apply/drop since nothing was stashed
        mock_git.has_uncommitted_changes.assert_not_called()
        mock_git.stash_push.assert_called_once()
        mock_git.stash_apply.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_task_branch_conflict_returns_conflict_result(mock_repos, sample_task, sample_slot):
    """Test rebase_task_branch returns CONFLICT outcome when rebase has conflicts."""
    from devboard.integrations.shell import RebaseConflictError
    from devboard.services.task_git_service import RebaseOutcome, RebaseResult

    worktree_slot_repo, _, _ = mock_repos
    sample_task.last_used_worktree_slot = sample_slot

    with patch("devboard.services.task_git.rebase_coordinator.GitRepoIntegration") as mock_git_class:
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git

        # is_rebase_in_progress is sync, must be a regular Mock
        mock_git.is_rebase_in_progress = Mock(return_value=False)
        # stash_push returns a ref (changes were stashed)
        mock_git.stash_push.return_value = "abc1234"
        mock_git.rebase_branch.side_effect = RebaseConflictError("Rebase conflict on file.txt")
        mock_git.get_conflicted_files.return_value = ["file.txt"]
        mock_git.find_stash_by_message.return_value = "stash@{0}"

        # Execute
        result = await TaskGitService.rebase_task_branch(sample_task)

        # Verify result indicates conflict with pending stash
        assert isinstance(result, RebaseResult)
        assert result.outcome == RebaseOutcome.CONFLICT
        assert result.conflicted_files == ["file.txt"]
        assert result.has_pending_stash is True

        # Verify stash was created before rebase
        mock_git.stash_push.assert_called_once()


@pytest.mark.asyncio
async def test_rebase_task_branch_stash_apply_conflict(mock_repos, sample_task, sample_slot):
    """Test rebase_task_branch handles stash apply conflicts."""
    from devboard.integrations.shell import ShellCommandExecutionError
    from devboard.services.task_git_service import RebaseOutcome, RebaseResult

    worktree_slot_repo, _, _ = mock_repos
    sample_task.last_used_worktree_slot = sample_slot

    with patch("devboard.services.task_git.rebase_coordinator.GitRepoIntegration") as mock_git_class:
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git

        # is_rebase_in_progress is sync, must be a regular Mock
        mock_git.is_rebase_in_progress = Mock(return_value=False)
        # stash_push returns a ref (changes were stashed)
        mock_git.stash_push.return_value = "abc1234"
        mock_git.rebase_branch.return_value = "newhead456"
        mock_git.find_stash_by_message.return_value = "stash@{0}"
        # Stash apply fails with conflict
        mock_git.stash_apply.side_effect = ShellCommandExecutionError("error: could not apply stash")
        mock_git.get_conflicted_files.return_value = ["conflicted_file.txt"]

        # Execute
        result = await TaskGitService.rebase_task_branch(sample_task)

        # Verify result indicates stash conflict
        assert isinstance(result, RebaseResult)
        assert result.outcome == RebaseOutcome.STASH_CONFLICT
        assert result.new_head == "newhead456"
        assert result.conflicted_files == ["conflicted_file.txt"]

        # Verify stash_push was called
        mock_git.stash_push.assert_called_once()
        mock_git.stash_apply.assert_called_once_with("stash@{0}")


@pytest.mark.asyncio
async def test_rebase_task_branch_no_branch_name_raises_error(mock_repos, sample_task):
    """Test rebase_task_branch raises ValueError when task has no branch name."""
    sample_task.branch_name = None

    with pytest.raises(ValueError, match="has no branch name configured"):
        await TaskGitService.rebase_task_branch(sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_prefers_most_recent_sticky_slot(service, mock_repos, sample_task, sample_codebase):
    """Test that when multiple slots have same last_used_by_task_id, the most recent is preferred.

    This scenario occurs when a task is checked out from a worktree to main repo:
    - Both slots have last_used_by_task_id set to the task
    - The main repo has a more recent last_used_at (from checkout)
    - Allocation should pick the main repo (most recent), not the worktree
    """
    worktree_slot_repo, task_repo, _ = mock_repos

    now = datetime.datetime.now(datetime.UTC)

    # Setup: Worktree slot - older last_used_at
    worktree_slot = MagicMock(spec=WorktreeSlot)
    worktree_slot.id = 1
    worktree_slot.path = "/projects/test-repo.worktree-1"
    worktree_slot.is_main_repo = False
    worktree_slot.locked = False
    worktree_slot.last_used_by_task_id = sample_task.id  # Same task
    worktree_slot.last_used_at = now - timedelta(hours=1)  # 1 hour ago
    worktree_slot.get_current_branch = AsyncMock(return_value="some-other-branch")

    # Setup: Main repo slot - more recent last_used_at (task was checked out here)
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.id = 2
    main_slot.path = sample_codebase.local_path
    main_slot.is_main_repo = True
    main_slot.locked = False
    main_slot.last_used_by_task_id = sample_task.id  # Same task
    main_slot.last_used_at = now  # Just now (more recent)
    main_slot.get_current_branch = AsyncMock(return_value=sample_task.branch_name)  # Branch matches

    # Return both slots (order doesn't matter since we sort by last_used_at)
    worktree_slot_repo.get_by_codebase.return_value = [worktree_slot, main_slot]
    worktree_slot_repo.lock_slot.return_value = main_slot

    # Mock git operations
    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute
        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Main slot (most recent) was selected, not worktree slot
    assert result == AllocationResult(slot=main_slot, reused=True)
    worktree_slot_repo.lock_slot.assert_called_once_with(main_slot, sample_task)


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_rolls_back_on_checkout_failure(service, mock_repos, sample_task, sample_slot):
    """Test that worktree is rolled back if checkout in main repo fails."""
    worktree_slot_repo, _, _ = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    with patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_class:
        main_git = AsyncMock()
        worktree_git = AsyncMock()

        worktree_path = "/projects/test-repo.worktree-1"

        def create_git(path):
            if path == sample_task.codebase.local_path:
                return main_git
            return worktree_git

        mock_git_class.side_effect = create_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False
        # But checkout fails
        main_git.checkout_branch.side_effect = Exception("Checkout failed")

        # Mock release_branch_from_worktree - returns stash SHA
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path=worktree_path,
            stash_sha="abc123stashsha",
        )

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Checkout failed"):
            await service.checkout_task_to_main_repo(sample_task)

        # Verify: ROLLBACK - Branch was checked back out in worktree
        worktree_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: ROLLBACK - Stash was applied back to worktree
        worktree_git.stash_apply.assert_called_once_with("abc123stashsha")

        # Verify: Slot was NOT assigned (operation failed)
        worktree_slot_repo.assign_slot.assert_not_called()


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_rolls_back_on_stash_apply_failure(
    service, mock_repos, sample_task, sample_slot
):
    """Test that worktree is rolled back if stash apply in main repo fails."""
    worktree_slot_repo, _, _ = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    with patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_class:
        main_git = AsyncMock()
        worktree_git = AsyncMock()

        worktree_path = "/projects/test-repo.worktree-1"

        def create_git(path):
            if path == sample_task.codebase.local_path:
                return main_git
            return worktree_git

        mock_git_class.side_effect = create_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False
        # Checkout succeeds but stash apply fails
        main_git.stash_apply.side_effect = Exception("Stash apply failed")

        # Mock release_branch_from_worktree - returns stash SHA
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path=worktree_path,
            stash_sha="abc123stashsha",
        )

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Stash apply failed"):
            await service.checkout_task_to_main_repo(sample_task)

        # Verify: Main repo checkout was attempted
        main_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: ROLLBACK - Branch was checked back out in worktree
        worktree_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: ROLLBACK - Stash was applied back to worktree
        worktree_git.stash_apply.assert_called_once_with("abc123stashsha")

        # Verify: Slot was NOT assigned (operation failed)
        worktree_slot_repo.assign_slot.assert_not_called()


@pytest.mark.asyncio
async def test_allocate_uses_main_repo_assigned_but_not_locked_by_same_task(
    service, mock_repos, sample_task, sample_codebase
):
    """Test that allocate_for_task uses main repo slot assigned to same task (sticky slot)."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: max_worktrees > 0 (normal mode, main repo excluded from automatic allocation)
    sample_codebase.max_worktrees = 2
    sample_task.codebase = sample_codebase

    # Setup: Main repo slot exists, assigned to this task but NOT locked
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.id = 1
    main_slot.path = sample_codebase.local_path
    main_slot.is_main_repo = True
    main_slot.locked = False  # Not locked
    main_slot.last_used_by_task_id = sample_task.id  # But assigned to this task
    main_slot.last_used_at = datetime.datetime.now(datetime.UTC)
    main_slot.get_current_branch = AsyncMock(return_value=sample_task.branch_name)

    worktree_slot_repo.get_by_codebase.return_value = [main_slot]
    worktree_slot_repo.lock_slot.return_value = main_slot

    # Mock git operations
    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=None)
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute
        result = await service._pool_manager.allocate_for_task(sample_task)

    # Verify: Main slot was used (sticky slot with matching branch)
    assert result == AllocationResult(slot=main_slot, reused=True)
    worktree_slot_repo.lock_slot.assert_called_once_with(main_slot, sample_task)


# =============================================================================
# Session Migration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_migrates_claude_session(service, mock_repos, sample_task, sample_slot):
    """Test that Claude Code session is migrated when moving task from worktree to main repo."""
    worktree_slot_repo, _, conversation_repo = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    # Setup: Task has active Claude Code conversation
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.CLAUDE_CODE
    mock_conversation.external_session_id = "test-session-123"
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with (
        patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_class,
        patch("devboard.services.workspace.workspace_service.ClaudeCodeSessionMigrator") as mock_session_service_class,
    ):
        main_git = AsyncMock()
        mock_git_class.return_value = main_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree - returns result indicating branch was in worktree
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path="/projects/test-repo.worktree-1",
            stash_sha=None,
        )

        # Mock session service
        mock_session_service = AsyncMock()
        mock_session_service_class.return_value = mock_session_service

        # Execute
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: Session was migrated (without old_working_dir - it's auto-detected)
        mock_session_service.migrate_session_to_directory.assert_called_once_with(
            session_id="test-session-123",
            new_working_dir=sample_task.codebase.local_path,
        )


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_skips_migration_for_internal_engine(
    service, mock_repos, sample_task, sample_slot
):
    """Test that session migration is skipped when task uses INTERNAL engine."""
    worktree_slot_repo, _, conversation_repo = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    # Setup: Task has active INTERNAL conversation (not Claude Code)
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.INTERNAL
    mock_conversation.external_session_id = None
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with (
        patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_class,
        patch("devboard.services.workspace.workspace_service.ClaudeCodeSessionMigrator") as mock_session_service_class,
    ):
        main_git = AsyncMock()
        mock_git_class.return_value = main_git

        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(None, None)

        # Execute
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: Session service was NOT called (INTERNAL engine)
        mock_session_service_class.assert_not_called()


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_handles_no_session_file(service, mock_repos, sample_task):
    """Test that checkout handles gracefully when no session file exists."""
    worktree_slot_repo, _, conversation_repo = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    # Setup: Task has active Claude Code conversation
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.CLAUDE_CODE
    mock_conversation.external_session_id = "test-session-123"
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with (
        patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_class,
        patch("devboard.services.workspace.workspace_service.ClaudeCodeSessionMigrator") as mock_session_service_class,
    ):
        main_git = AsyncMock()
        mock_git_class.return_value = main_git
        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(None, None)

        # Mock session service to raise FileNotFoundError (no session file)
        mock_session_service = AsyncMock()
        mock_session_service.migrate_session_to_directory.side_effect = FileNotFoundError("Session not found")
        mock_session_service_class.return_value = mock_session_service

        # Execute - should not raise
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: Session migration was attempted but handled gracefully
        mock_session_service.migrate_session_to_directory.assert_called_once()


@pytest.mark.asyncio
async def test_migrate_claude_session_if_needed_skips_when_no_external_session_id(service, mock_repos, sample_task):
    """Test that session migration is skipped when conversation has no external_session_id."""
    _, _, conversation_repo = mock_repos

    # Setup: Task has Claude Code conversation but no external_session_id
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.CLAUDE_CODE
    mock_conversation.external_session_id = None  # No session ID
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with patch("devboard.services.workspace.workspace_service.ClaudeCodeSessionMigrator") as mock_session_service_class:
        # Execute
        await service._migrate_claude_session_if_needed(
            task=sample_task,
            new_working_dir="/new/path",
        )

        # Verify: Session service was NOT instantiated
        mock_session_service_class.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_claude_session_if_needed_skips_when_no_active_conversation(service, mock_repos, sample_task):
    """Test that session migration is skipped when task has no active conversation."""
    _, _, conversation_repo = mock_repos

    # Setup: No active conversation
    conversation_repo.get_active_conversation_for_entity.return_value = None

    with patch("devboard.services.workspace.workspace_service.ClaudeCodeSessionMigrator") as mock_session_service_class:
        # Execute
        await service._migrate_claude_session_if_needed(
            task=sample_task,
            new_working_dir="/new/path",
        )

        # Verify: Session service was NOT instantiated
        mock_session_service_class.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_claude_session_if_needed_handles_file_not_found(service, mock_repos, sample_task):
    """Test that session migration handles FileNotFoundError gracefully."""
    _, _, conversation_repo = mock_repos

    # Setup: Task has Claude Code conversation
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.CLAUDE_CODE
    mock_conversation.external_session_id = "test-session-123"
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with patch("devboard.services.workspace.workspace_service.ClaudeCodeSessionMigrator") as mock_session_service_class:
        mock_session_service = AsyncMock()
        mock_session_service.migrate_session_to_directory.side_effect = FileNotFoundError("Session not found")
        mock_session_service_class.return_value = mock_session_service

        # Execute - should not raise
        await service._migrate_claude_session_if_needed(
            task=sample_task,
            new_working_dir="/new/path",
        )

        # Verify: Session migration was attempted
        mock_session_service.migrate_session_to_directory.assert_called_once()


# =============================================================================
# Setup Command Tests
# =============================================================================


@pytest.mark.asyncio
async def test_run_setup_command_success(service, mock_repos, sample_task, sample_slot, sample_codebase):
    """Test _run_setup_command executes setup command successfully."""
    sample_codebase.setup_command = "npm install"

    with patch(
        "devboard.services.workspace.workspace_service.execute_shell_command", new_callable=AsyncMock
    ) as mock_exec:
        from devboard.integrations.shell import ShellCommandResult

        mock_exec.return_value = ShellCommandResult(stdout="Success", stderr="", returncode=0)

        # Should not raise
        await service._run_setup_command(sample_slot, sample_codebase, sample_task)

        mock_exec.assert_called_once_with(
            command=["bash", "-c", "npm install"],
            working_dir=sample_slot.path,
            timeout=300.0,
            raise_on_error=False,
        )


@pytest.mark.asyncio
async def test_run_setup_command_failure(service, mock_repos, sample_task, sample_slot, sample_codebase):
    """Test _run_setup_command raises SetupCommandError on failure."""
    from devboard.services.workspace import SetupCommandError

    sample_codebase.setup_command = "npm install"

    with patch(
        "devboard.services.workspace.workspace_service.execute_shell_command", new_callable=AsyncMock
    ) as mock_exec:
        from devboard.integrations.shell import ShellCommandResult

        mock_exec.return_value = ShellCommandResult(stdout="", stderr="npm ERR! code ENOENT", returncode=1)

        with pytest.raises(SetupCommandError) as exc_info:
            await service._run_setup_command(sample_slot, sample_codebase, sample_task)

        assert "npm ERR! code ENOENT" in exc_info.value.message
        assert exc_info.value.command == "npm install"
        assert exc_info.value.returncode == 1


@pytest.mark.asyncio
async def test_run_setup_command_no_command_configured(service, mock_repos, sample_task, sample_slot, sample_codebase):
    """Test _run_setup_command does nothing when no setup command is configured."""
    sample_codebase.setup_command = None

    with patch(
        "devboard.services.workspace.workspace_service.execute_shell_command", new_callable=AsyncMock
    ) as mock_exec:
        # Should not raise
        await service._run_setup_command(sample_slot, sample_codebase, sample_task)

        mock_exec.assert_not_called()


@pytest.mark.asyncio
async def test_prepare_workspace_setup_failure_raises_error(service, sample_task, sample_slot):
    """Test that prepare_workspace raises SetupCommandError when setup fails."""
    from devboard.services.workspace import SetupCommandError

    sample_task.codebase.setup_command = "npm install"

    with (
        patch.object(service, "_check_worktree_valid", return_value=True),
        patch.object(service, "checkout_branch_in_slot", new_callable=AsyncMock, return_value=True),
        patch.object(service, "_run_setup_command", new_callable=AsyncMock) as mock_setup,
        patch.object(service, "_migrate_claude_session_if_needed", new_callable=AsyncMock),
    ):
        mock_setup.side_effect = SetupCommandError(
            message="npm ERR! missing package.json",
            command="npm install",
            returncode=1,
        )

        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        with pytest.raises(SetupCommandError) as exc_info:
            async for _ in service.prepare_workspace(task=sample_task, slot=sample_slot):
                pass

    assert exc_info.value.message == "npm ERR! missing package.json"


@pytest.mark.asyncio
async def test_prepare_workspace_skips_setup_when_no_checkout_and_no_creation(service, sample_task, sample_slot):
    """Test that setup is skipped when slot is valid and already on the correct branch."""
    sample_task.codebase.setup_command = "npm install"

    with (
        patch.object(service, "_check_worktree_valid", return_value=True),
        patch.object(service, "checkout_branch_in_slot", new_callable=AsyncMock, return_value=False),
        patch.object(service, "_run_setup_command", new_callable=AsyncMock) as mock_setup,
        patch.object(service, "_migrate_claude_session_if_needed", new_callable=AsyncMock),
    ):

        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        events = []
        async for event in service.prepare_workspace(task=sample_task, slot=sample_slot):
            events.append(event)

    system_events = [e for e in events if isinstance(e, SystemEvent)]
    assert len(system_events) == 0
    mock_setup.assert_not_called()


@pytest.mark.asyncio
async def test_prepare_workspace_skips_setup_when_not_configured(service, sample_task, sample_slot):
    """Test that setup is skipped when no setup command is configured."""
    sample_task.codebase.setup_command = None

    with (
        patch.object(service, "_check_worktree_valid", return_value=True),
        patch.object(service, "checkout_branch_in_slot", new_callable=AsyncMock, return_value=True),
        patch.object(service, "_run_setup_command", new_callable=AsyncMock),
        patch.object(service, "_migrate_claude_session_if_needed", new_callable=AsyncMock),
    ):

        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        events = []
        async for event in service.prepare_workspace(task=sample_task, slot=sample_slot):
            events.append(event)

    system_events = [e for e in events if isinstance(e, SystemEvent)]
    setup_events = [e for e in system_events if e.type == SystemEventType.WORKSPACE_SETUP]
    assert len(setup_events) == 0


# =============================================================================
# checkout_branch_in_slot Tests
# =============================================================================


class TestCheckoutBranchInSlot:
    """Tests for WorkspaceService.checkout_branch_in_slot."""

    @pytest.mark.asyncio
    async def test_already_on_correct_branch_returns_false(self, service, sample_slot):
        """Returns False immediately when the slot is already on the target branch."""
        with patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_cls:
            mock_git = mock_git_cls.return_value
            mock_git.get_current_branch = AsyncMock(return_value="feature/target-branch")
            mock_git.get_in_progress_operation_branch = AsyncMock(return_value=None)
            mock_git.checkout_branch = AsyncMock()

            result = await service.checkout_branch_in_slot(sample_slot, "feature/target-branch")

        assert result is False
        mock_git.checkout_branch.assert_not_called()

    @pytest.mark.asyncio
    async def test_in_progress_operation_matches_target_returns_false(self, service, sample_slot):
        """Returns False without checkout when an in-progress git operation is on the target branch."""
        with patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_cls:
            mock_git = mock_git_cls.return_value
            # HEAD is detached (e.g. during rebase), current branch reports as "HEAD"
            mock_git.get_current_branch = AsyncMock(return_value="HEAD")
            mock_git.get_in_progress_operation_branch = AsyncMock(return_value="feature/target-branch")
            mock_git.checkout_branch = AsyncMock()

            result = await service.checkout_branch_in_slot(sample_slot, "feature/target-branch")

        assert result is False
        mock_git.checkout_branch.assert_not_called()

    @pytest.mark.asyncio
    async def test_in_progress_operation_different_branch_proceeds_with_checkout(self, service, sample_slot):
        """Performs checkout when an in-progress operation is on a different branch."""
        with patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_cls:
            mock_git = mock_git_cls.return_value
            mock_git.get_current_branch = AsyncMock(return_value="HEAD")
            mock_git.get_in_progress_operation_branch = AsyncMock(return_value="feature/other-branch")
            mock_git.checkout_branch = AsyncMock()

            result = await service.checkout_branch_in_slot(sample_slot, "feature/target-branch")

        assert result is True
        mock_git.checkout_branch.assert_called_once_with("feature/target-branch")

    @pytest.mark.asyncio
    async def test_no_in_progress_operation_wrong_branch_proceeds_with_checkout(self, service, sample_slot):
        """Performs checkout when on a different branch with no in-progress operation."""
        with patch("devboard.services.workspace.workspace_service.GitRepoIntegration") as mock_git_cls:
            mock_git = mock_git_cls.return_value
            mock_git.get_current_branch = AsyncMock(return_value="main")
            mock_git.get_in_progress_operation_branch = AsyncMock(return_value=None)
            mock_git.checkout_branch = AsyncMock()

            result = await service.checkout_branch_in_slot(sample_slot, "feature/target-branch")

        assert result is True
        mock_git.checkout_branch.assert_called_once_with("feature/target-branch")
        mock_git_cls.assert_called_once_with(sample_slot.path)
