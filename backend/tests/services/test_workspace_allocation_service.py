"""Tests for WorkspaceAllocationService."""

import datetime
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from devboard.db.models import Codebase, Task, WorktreeSlot
from devboard.services.workspace_allocation_service import (
    AllSlotsLockedException,
    WorkspaceAllocationService,
)


@pytest.fixture
def mock_repos():
    """Create mock repositories."""
    worktree_slot_repo = MagicMock()
    task_repo = MagicMock()
    return worktree_slot_repo, task_repo


@pytest.fixture
def service(mock_repos):
    """Create service instance with mocked repos."""
    worktree_slot_repo, task_repo = mock_repos
    return WorkspaceAllocationService(
        worktree_slot_repo=worktree_slot_repo,
        task_repo=task_repo,
    )


@pytest.fixture
def sample_codebase():
    """Create a sample codebase."""
    codebase = MagicMock(spec=Codebase)
    codebase.id = 1
    codebase.local_path = "/projects/test-repo"
    codebase.name = "Test Repo"
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
    """Create a sample worktree slot."""
    slot = MagicMock(spec=WorktreeSlot)
    slot.id = 1
    slot.path = "/projects/test-repo"
    slot.is_main_repo = True
    slot.locked_by_task_id = None
    slot.last_used_by_task_id = None
    slot.get_current_branch = MagicMock(return_value="main")
    return slot


@pytest.mark.asyncio
async def test_allocate_for_task_sticky_slot(service, mock_repos, sample_task, sample_codebase, sample_slot):
    """Test allocation with task stickiness (prefer previously used slot)."""
    worktree_slot_repo, task_repo = mock_repos

    # Setup: Task previously used this slot
    sample_slot.last_used_by_task_id = sample_task.id
    sample_slot.locked = False  # Available
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot  # Return same slot after locking
    # Mock git dirty check (clean slot)
    with patch("devboard.services.workspace_allocation_service.CodebaseIntegration") as mock_git:
        mock_git.return_value.has_uncommitted_changes.return_value = False

        # Execute (no branch checkout - that's caller's responsibility)
        result = await service.allocate_for_task(sample_task)

    # Verify: Returned the sticky slot
    assert result.id == sample_slot.id
    worktree_slot_repo.lock_slot.assert_called_once_with(sample_slot, sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_branch_optimization(service, mock_repos, sample_task, sample_codebase, sample_slot):
    """Test allocation with branch optimization (slot already on base branch)."""
    worktree_slot_repo, task_repo = mock_repos

    # Setup: No sticky slot, but slot already on base branch
    sample_slot.locked = False  # Available
    sample_slot.last_used_by_task_id = 99  # Not this task
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot  # Return same slot after locking
    # Mock the slot's current branch to match task's base branch
    sample_slot.get_current_branch.return_value = sample_task.base_branch

    # Mock git dirty check (clean slot)
    with patch("devboard.services.workspace_allocation_service.CodebaseIntegration") as mock_git:
        mock_git.return_value.has_uncommitted_changes.return_value = False

        # Execute - should use branch optimization
        result = await service.allocate_for_task(sample_task)

    # Verify: Used branch optimization
    assert result.id == sample_slot.id
    worktree_slot_repo.lock_slot.assert_called_once_with(sample_slot, sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_all_slots_locked(service, mock_repos, sample_task, sample_codebase):
    """Test allocation when all slots are locked."""
    worktree_slot_repo, task_repo = mock_repos

    # Setup: All slots are locked (empty available_slots)
    locked_slot = MagicMock(spec=WorktreeSlot)
    locked_slot.locked = True
    locked_slot.last_used_by_task = MagicMock()
    locked_slot.last_used_by_task.id = 2
    locked_slot.last_used_by_task.title = "Other Task"
    locked_slot.path = "/projects/test-repo"

    worktree_slot_repo.get_by_codebase.return_value = [locked_slot]  # Only locked slots
    # Execute and verify exception
    with pytest.raises(AllSlotsLockedException) as exc_info:
        await service.allocate_for_task(sample_task)

    assert exc_info.value.can_create_new is True


@pytest.mark.asyncio
async def test_cleanup_stale_locks(service, mock_repos, sample_codebase):
    """Test cleanup of stale locks for tasks with no active conversations."""
    worktree_slot_repo, task_repo = mock_repos

    # Setup: Locked slot from 2 hours ago
    locked_slot = MagicMock(spec=WorktreeSlot)
    locked_slot.id = 1
    locked_slot.locked_by_task_id = 1
    locked_slot.locked_at = datetime.datetime.now(datetime.UTC) - timedelta(hours=2)

    worktree_slot_repo.get_all_locked_for_codebase.return_value = [locked_slot]

    # Mock task with no active conversations
    task = MagicMock()
    task.id = 1
    task_repo.get.return_value = task
    task_repo.get_tasks_with_active_conversations.return_value = []  # No active conversations

    # Execute
    released_count = await service.cleanup_stale_locks(sample_codebase.id)

    # Verify: Lock was released
    assert released_count == 1
    worktree_slot_repo.unlock_slot.assert_called_once_with(locked_slot)


@pytest.mark.asyncio
async def test_cleanup_stale_locks_old_locks(service, mock_repos, sample_codebase):
    """Test cleanup of locks older than 24 hours (failsafe)."""
    worktree_slot_repo, task_repo = mock_repos

    # Setup: Very old locked slot (25 hours ago)
    old_locked_slot = MagicMock(spec=WorktreeSlot)
    old_locked_slot.id = 1
    old_locked_slot.locked_by_task_id = 1
    old_locked_slot.locked_at = datetime.datetime.now(datetime.UTC) - timedelta(hours=25)

    worktree_slot_repo.get_all_locked_for_codebase.return_value = [old_locked_slot]

    # Even if task has active conversations, old lock should be released
    task = MagicMock()
    task.id = 1
    task_repo.get.return_value = task
    active_task = MagicMock()
    active_task.id = 1
    task_repo.get_tasks_with_active_conversations.return_value = [active_task]

    # Execute
    released_count = await service.cleanup_stale_locks(sample_codebase.id)

    # Verify: Old lock was released despite active conversation (24h failsafe)
    assert released_count == 1
    worktree_slot_repo.unlock_slot.assert_called_once_with(old_locked_slot)


def test_bootstrap_main_repo_slot(service, mock_repos, sample_codebase):
    """Test bootstrapping main repo slot when none exists."""
    worktree_slot_repo, task_repo = mock_repos

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
    service.bootstrap_main_repo_slot(sample_codebase)

    # Verify: Created main repo slot
    worktree_slot_repo.create.assert_called_once()


def test_release_slot(service, mock_repos):
    """Test releasing a slot."""
    worktree_slot_repo, task_repo = mock_repos

    # Setup: Mock slot
    slot = MagicMock(spec=WorktreeSlot)
    slot.id = 1

    # Execute (not async) - now takes WorktreeSlot instance
    service.release_slot(slot)

    # Verify: Unlocked the slot
    worktree_slot_repo.unlock_slot.assert_called_once_with(slot)
