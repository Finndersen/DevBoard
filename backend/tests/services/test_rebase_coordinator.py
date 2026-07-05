"""Tests for TaskRebaseCoordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.db.models import Task
from devboard.db.models.task import NoWorktreeAllocatedException
from devboard.db.models.worktree_slot import WorktreeSlot
from devboard.services.task_git.rebase_coordinator import TaskRebaseCoordinator
from devboard.services.task_git.types import RebaseOutcome, TaskConfigurationError


@pytest.fixture
def mock_task():
    task = MagicMock(spec=Task)
    task.id = 42
    task.branch_name = "feature/my-task"
    task.base_branch = "main"
    task.codebase = MagicMock()
    task.codebase.local_path = "/repo"
    return task


@pytest.fixture
def mock_slot():
    slot = MagicMock(spec=WorktreeSlot)
    slot.path = "/repo/.worktrees/slot-1"
    return slot


class TestRebaseTaskBranch:
    @pytest.mark.asyncio
    async def test_raises_no_worktree_exception_when_no_slot(self, mock_task):
        """Task with no workspace allocated → raises NoWorktreeAllocatedException."""
        mock_task.last_used_worktree_slot = None

        with pytest.raises(NoWorktreeAllocatedException, match="no workspace allocated"):
            await TaskRebaseCoordinator.rebase_task_branch(mock_task)

    @pytest.mark.asyncio
    async def test_raises_task_configuration_error_when_no_branch_name(self, mock_task, mock_slot):
        """Task with no branch name → raises TaskConfigurationError."""
        mock_task.branch_name = None
        mock_task.last_used_worktree_slot = mock_slot

        with pytest.raises(TaskConfigurationError, match="no branch name"):
            await TaskRebaseCoordinator.rebase_task_branch(mock_task)

    @pytest.mark.asyncio
    async def test_uses_slot_path_when_slot_present(self, mock_task, mock_slot):
        """Task with a slot → rebase runs in slot.path, NOT codebase.local_path."""
        mock_task.last_used_worktree_slot = mock_slot
        mock_task.codebase.local_path = "/repo"

        with patch("devboard.services.task_git.rebase_coordinator.GitRepoIntegration") as mock_git_cls:
            mock_git = mock_git_cls.return_value
            mock_git.is_rebase_in_progress.return_value = False
            mock_git.stash_push = AsyncMock(return_value=None)
            mock_git.get_fork_point = AsyncMock(return_value="abc123")
            mock_git.get_changed_file_paths = AsyncMock(return_value=[])
            mock_git.list_remotes = AsyncMock(return_value=[])
            mock_git.get_branch_head = AsyncMock(return_value="abc123")
            mock_git.rebase_branch = AsyncMock(return_value="def456")
            mock_git.find_stash_by_message = AsyncMock(return_value=None)

            result = await TaskRebaseCoordinator.rebase_task_branch(mock_task)

        # GitRepoIntegration must be constructed with the slot path, NOT main repo path
        mock_git_cls.assert_called_once_with(mock_slot.path)
        assert result.outcome == RebaseOutcome.SUCCESS
        assert result.slot_path == mock_slot.path
