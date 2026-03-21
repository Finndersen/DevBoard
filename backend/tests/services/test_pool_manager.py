"""Tests for WorktreePoolManager."""

import datetime
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.config.integration_configs import WorktreeLocationMode
from devboard.db.models import Codebase, Task, WorktreeSlot
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.services.workspace.pool_manager import WorktreePoolManager
from devboard.services.workspace.types import BranchInUseException


@pytest.fixture
def worktree_slot_repo():
    return MagicMock(spec=WorktreeSlotRepository)


@pytest.fixture
def pool_manager(worktree_slot_repo):
    return WorktreePoolManager(worktree_slot_repo=worktree_slot_repo)


@pytest.fixture
def sample_codebase():
    codebase = MagicMock(spec=Codebase)
    codebase.id = 1
    codebase.local_path = "/projects/test-repo"
    codebase.max_worktrees = 2
    return codebase


@pytest.fixture
def sample_task(sample_codebase):
    task = MagicMock(spec=Task)
    task.id = 100
    task.branch_name = "handle-viewing-claude-code-sessions-with"
    task.codebase = sample_codebase
    return task


def _make_slot(slot_id: int, path: str, locked: bool, last_used_by_task_id: int | None) -> MagicMock:
    slot = MagicMock(spec=WorktreeSlot)
    slot.id = slot_id
    slot.path = path
    slot.is_main_repo = False
    slot.locked = locked
    slot.last_used_by_task_id = last_used_by_task_id
    slot.last_used_at = datetime.datetime.now(datetime.UTC)
    return slot


# =============================================================================
# Branch-Location Priority: Stale Same-Task Lock Re-acquisition
# =============================================================================


@pytest.mark.asyncio
async def test_allocate_reacquires_stale_lock_for_same_task(pool_manager, worktree_slot_repo, sample_task):
    """Branch is locked by the same task (stale) — should re-acquire, not raise."""
    slot = _make_slot(
        slot_id=1,
        path="/projects/test-repo.worktree-1",
        locked=True,
        last_used_by_task_id=sample_task.id,  # same task
    )
    worktree_slot_repo.get_by_codebase.return_value = [slot]
    worktree_slot_repo.get_all_locked.return_value = []  # no stale cleanup
    worktree_slot_repo.lock_slot.return_value = slot

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=slot.path)

        result = await pool_manager.allocate_for_task(sample_task)

    assert result is slot
    worktree_slot_repo.lock_slot.assert_called_once_with(slot, sample_task)


@pytest.mark.asyncio
async def test_allocate_raises_branch_in_use_for_different_task(pool_manager, worktree_slot_repo, sample_task):
    """Branch is locked by a different task — should raise BranchInUseException."""
    other_task_id = 999
    slot = _make_slot(
        slot_id=1,
        path="/projects/test-repo.worktree-1",
        locked=True,
        last_used_by_task_id=other_task_id,
    )
    worktree_slot_repo.get_by_codebase.return_value = [slot]
    worktree_slot_repo.get_all_locked.return_value = []

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=slot.path)

        with pytest.raises(BranchInUseException, match=str(other_task_id)):
            await pool_manager.allocate_for_task(sample_task)

    worktree_slot_repo.lock_slot.assert_not_called()


@pytest.mark.asyncio
async def test_allocate_uses_unlocked_slot_with_branch_already_checked_out(
    pool_manager, worktree_slot_repo, sample_task
):
    """Branch is in an unlocked slot — should allocate normally."""
    slot = _make_slot(
        slot_id=1,
        path="/projects/test-repo.worktree-1",
        locked=False,
        last_used_by_task_id=None,
    )
    worktree_slot_repo.get_by_codebase.return_value = [slot]
    worktree_slot_repo.get_all_locked.return_value = []
    worktree_slot_repo.lock_slot.return_value = slot

    with patch("devboard.services.workspace.pool_manager.GitRepoIntegration") as mock_git:
        mock_git.return_value.get_checked_out_location = AsyncMock(return_value=slot.path)

        result = await pool_manager.allocate_for_task(sample_task)

    assert result is slot
    worktree_slot_repo.lock_slot.assert_called_once_with(slot, sample_task)


# =============================================================================
# Worktree Path Generation
# =============================================================================


_WORKTREE_SUFFIX_RE = re.compile(r"\.worktree-[0-9a-f]{7}$")


def test_generate_new_worktree_path_central_mode(worktree_slot_repo, sample_codebase, monkeypatch):
    """Central mode generates path under DEVBOARD_HOME/worktrees/ with a UUID suffix."""
    monkeypatch.setenv("DEVBOARD_HOME", "/devboard")

    manager = WorktreePoolManager(
        worktree_slot_repo=worktree_slot_repo, worktree_location_mode=WorktreeLocationMode.CENTRAL
    )

    with patch("devboard.services.workspace.pool_manager.Path.mkdir") as mock_mkdir:
        path = manager._generate_new_worktree_path(sample_codebase)

    assert Path(path).parent == Path("/devboard/worktrees")
    assert Path(path).name.startswith("test-repo.worktree-")
    assert _WORKTREE_SUFFIX_RE.search(path)
    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


def test_generate_new_worktree_path_central_mode_produces_unique_paths(
    worktree_slot_repo, sample_codebase, monkeypatch
):
    """Two consecutive calls produce different paths."""
    monkeypatch.setenv("DEVBOARD_HOME", "/devboard")

    manager = WorktreePoolManager(
        worktree_slot_repo=worktree_slot_repo, worktree_location_mode=WorktreeLocationMode.CENTRAL
    )

    with patch("devboard.services.workspace.pool_manager.Path.mkdir"):
        path1 = manager._generate_new_worktree_path(sample_codebase)
        path2 = manager._generate_new_worktree_path(sample_codebase)

    assert path1 != path2


def test_generate_new_worktree_path_alongside_mode(worktree_slot_repo, sample_codebase):
    """Alongside mode generates path as sibling to main repo with a UUID suffix."""
    manager = WorktreePoolManager(
        worktree_slot_repo=worktree_slot_repo, worktree_location_mode=WorktreeLocationMode.ALONGSIDE
    )

    path = manager._generate_new_worktree_path(sample_codebase)

    assert Path(path).parent == Path("/projects")
    assert Path(path).name.startswith("test-repo.worktree-")
    assert _WORKTREE_SUFFIX_RE.search(path)


def test_generate_new_worktree_path_central_mode_falls_back_to_home(worktree_slot_repo, sample_codebase, monkeypatch):
    """Central mode falls back to ~/.devboard when DEVBOARD_HOME is not set."""
    monkeypatch.delenv("DEVBOARD_HOME", raising=False)

    manager = WorktreePoolManager(worktree_slot_repo=worktree_slot_repo)

    with patch("devboard.services.workspace.pool_manager.Path.mkdir"):
        path = manager._generate_new_worktree_path(sample_codebase)

    expected_parent = Path.home() / ".devboard" / "worktrees"
    assert Path(path).parent == expected_parent
    assert Path(path).name.startswith("test-repo.worktree-")
    assert _WORKTREE_SUFFIX_RE.search(path)


# =============================================================================
# Bootstrap Main Repo Slot
# =============================================================================


def test_bootstrap_creates_main_slot_when_none_exists(pool_manager, worktree_slot_repo, sample_codebase):
    """No main slot exists — creates a new one."""
    worktree_slot_repo.get_main_slot_for_codebase.side_effect = ValueError("No main repo slot found")
    new_slot = _make_slot(slot_id=1, path=sample_codebase.local_path, locked=False, last_used_by_task_id=None)
    new_slot.is_main_repo = True
    worktree_slot_repo.create.return_value = new_slot

    result = pool_manager.bootstrap_main_repo_slot(sample_codebase)

    assert result is new_slot
    worktree_slot_repo.create.assert_called_once_with(
        codebase_id=sample_codebase.id,
        path=sample_codebase.local_path,
        is_main_repo=True,
    )


def test_bootstrap_returns_existing_main_slot(pool_manager, worktree_slot_repo, sample_codebase):
    """Existing main slot — returned directly without creating."""
    existing = _make_slot(slot_id=1, path=sample_codebase.local_path, locked=False, last_used_by_task_id=None)
    existing.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = existing

    result = pool_manager.bootstrap_main_repo_slot(sample_codebase)

    assert result is existing
    worktree_slot_repo.create.assert_not_called()
