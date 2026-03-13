"""Tests for TaskGitService.get_task_git_status() uncommitted base overlap computation."""

from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest

from devboard.db.models.task import Task
from devboard.integrations.types import BranchComparison
from devboard.services.task_git.service import TaskGitService


@pytest.fixture
def mock_task():
    """Create a mock Task with codebase and worktree slot."""
    task = Mock(spec=Task)
    task.branch_name = "feature/test-branch"
    task.base_branch = "main"

    task.codebase = Mock()
    task.codebase.local_path = "/repo"

    slot = Mock()
    slot.path = "/worktrees/slot-1"
    type(task).last_used_worktree_slot = PropertyMock(return_value=slot)

    return task


@pytest.fixture
def mock_task_no_worktree():
    """Create a mock Task without a worktree slot."""
    task = Mock(spec=Task)
    task.branch_name = "feature/test-branch"
    task.base_branch = "main"

    task.codebase = Mock()
    task.codebase.local_path = "/repo"

    type(task).last_used_worktree_slot = PropertyMock(return_value=None)

    return task


@pytest.fixture
def default_comparison():
    """Default branch comparison with no conflicts."""
    return BranchComparison(ahead=1, behind=0, can_merge=True, has_conflicts=False)


class TestGetTaskGitStatusUncommittedOverlap:
    """Tests for has_uncommitted_base_overlap computation in get_task_git_status."""

    @pytest.mark.asyncio
    async def test_overlap_detected(self, mock_task, default_comparison):
        """has_uncommitted_base_overlap is True when uncommitted and base changes share files."""
        service = TaskGitService()

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=True)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)
            main_git.get_fork_point = AsyncMock(return_value="abc123")
            main_git.get_changed_file_paths = AsyncMock(return_value=["src/shared.py", "src/other.py"])

            worktree_git = Mock()
            worktree_git.is_rebase_in_progress = Mock(return_value=False)
            worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/shared.py", "src/local.py"])

            def side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return worktree_git
                return main_git

            MockGit.side_effect = side_effect

            status = await service.get_task_git_status(mock_task)

        assert status.has_uncommitted_base_overlap is True

    @pytest.mark.asyncio
    async def test_no_overlap(self, mock_task, default_comparison):
        """has_uncommitted_base_overlap is False when no shared files."""
        service = TaskGitService()

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=True)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)
            main_git.get_fork_point = AsyncMock(return_value="abc123")
            main_git.get_changed_file_paths = AsyncMock(return_value=["src/base_only.py"])

            worktree_git = Mock()
            worktree_git.is_rebase_in_progress = Mock(return_value=False)
            worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/local_only.py"])

            def side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return worktree_git
                return main_git

            MockGit.side_effect = side_effect

            status = await service.get_task_git_status(mock_task)

        assert status.has_uncommitted_base_overlap is False

    @pytest.mark.asyncio
    async def test_no_uncommitted_changes(self, mock_task, default_comparison):
        """has_uncommitted_base_overlap is False when no uncommitted changes."""
        service = TaskGitService()

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=False)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)

            worktree_git = Mock()
            worktree_git.is_rebase_in_progress = Mock(return_value=False)
            worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=[])

            def side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return worktree_git
                return main_git

            MockGit.side_effect = side_effect

            status = await service.get_task_git_status(mock_task)

        assert status.has_uncommitted_base_overlap is False

    @pytest.mark.asyncio
    async def test_no_worktree(self, mock_task_no_worktree, default_comparison):
        """has_uncommitted_base_overlap is False when no worktree exists."""
        service = TaskGitService()

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=True)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)

            MockGit.return_value = main_git

            status = await service.get_task_git_status(mock_task_no_worktree)

        assert status.has_uncommitted_base_overlap is False

    @pytest.mark.asyncio
    async def test_no_fork_point(self, mock_task, default_comparison):
        """has_uncommitted_base_overlap is False when fork point cannot be determined."""
        service = TaskGitService()

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=True)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)
            main_git.get_fork_point = AsyncMock(return_value=None)

            worktree_git = Mock()
            worktree_git.is_rebase_in_progress = Mock(return_value=False)
            worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/file.py"])

            def side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return worktree_git
                return main_git

            MockGit.side_effect = side_effect

            status = await service.get_task_git_status(mock_task)

        assert status.has_uncommitted_base_overlap is False
