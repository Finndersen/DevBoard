"""Tests for TaskGitService."""

from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest

from devboard.db.models.task import Task
from devboard.integrations.shell import ShellCommandExecutionError, ShellCommandTimeoutError
from devboard.integrations.types import BranchComparison
from devboard.services.task_git.service import TaskBranchNotFoundException, TaskGitService


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

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=True)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)
            main_git.get_fork_point = AsyncMock(return_value="abc123")
            main_git.get_changed_file_paths = AsyncMock(return_value=["src/shared.py", "src/other.py"])
            main_git.list_remotes = AsyncMock(return_value=["origin"])
            main_git.fetch = AsyncMock()

            worktree_git = Mock()
            worktree_git.is_rebase_in_progress = Mock(return_value=False)
            worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/shared.py", "src/local.py"])

            def side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return worktree_git
                return main_git

            MockGit.side_effect = side_effect

            status = await TaskGitService.get_task_git_status(mock_task)

        assert status.has_uncommitted_base_overlap is True

    @pytest.mark.asyncio
    async def test_no_overlap(self, mock_task, default_comparison):
        """has_uncommitted_base_overlap is False when no shared files."""

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=True)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)
            main_git.get_fork_point = AsyncMock(return_value="abc123")
            main_git.get_changed_file_paths = AsyncMock(return_value=["src/base_only.py"])
            main_git.list_remotes = AsyncMock(return_value=["origin"])
            main_git.fetch = AsyncMock()

            worktree_git = Mock()
            worktree_git.is_rebase_in_progress = Mock(return_value=False)
            worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/local_only.py"])

            def side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return worktree_git
                return main_git

            MockGit.side_effect = side_effect

            status = await TaskGitService.get_task_git_status(mock_task)

        assert status.has_uncommitted_base_overlap is False

    @pytest.mark.asyncio
    async def test_no_uncommitted_changes(self, mock_task, default_comparison):
        """has_uncommitted_base_overlap is False when no uncommitted changes."""

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=False)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)
            main_git.list_remotes = AsyncMock(return_value=["origin"])
            main_git.fetch = AsyncMock()

            worktree_git = Mock()
            worktree_git.is_rebase_in_progress = Mock(return_value=False)
            worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=[])

            def side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return worktree_git
                return main_git

            MockGit.side_effect = side_effect

            status = await TaskGitService.get_task_git_status(mock_task)

        assert status.has_uncommitted_base_overlap is False

    @pytest.mark.asyncio
    async def test_no_worktree(self, mock_task_no_worktree, default_comparison):
        """has_uncommitted_base_overlap is False when no worktree exists."""

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=True)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)
            main_git.list_remotes = AsyncMock(return_value=["origin"])
            main_git.fetch = AsyncMock()

            MockGit.return_value = main_git

            status = await TaskGitService.get_task_git_status(mock_task_no_worktree)

        assert status.has_uncommitted_base_overlap is False

    @pytest.mark.asyncio
    async def test_no_fork_point(self, mock_task, default_comparison):
        """has_uncommitted_base_overlap is False when fork point cannot be determined."""

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            main_git = Mock()
            main_git.has_uncommitted_changes = AsyncMock(return_value=True)
            main_git.get_current_branch = AsyncMock(return_value="main")
            main_git.branch_exists = AsyncMock(return_value=True)
            main_git.get_branch_comparison = AsyncMock(return_value=default_comparison)
            main_git.get_fork_point = AsyncMock(return_value=None)
            main_git.list_remotes = AsyncMock(return_value=["origin"])
            main_git.fetch = AsyncMock()

            worktree_git = Mock()
            worktree_git.is_rebase_in_progress = Mock(return_value=False)
            worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/file.py"])

            def side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return worktree_git
                return main_git

            MockGit.side_effect = side_effect

            status = await TaskGitService.get_task_git_status(mock_task)

        assert status.has_uncommitted_base_overlap is False


class TestCreateTaskBranch:
    """Tests for remote fetch behaviour in create_task_branch."""

    @pytest.mark.asyncio
    async def test_fetches_before_creating_branch(self, mock_task_no_worktree):
        """Fetch is called after branch_exists check but before branch creation."""
        mock_task_no_worktree.base_branch = "origin/main"
        call_order: list[str] = []
        fetch_kwargs: dict = {}

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.list_remotes = AsyncMock(return_value=["origin"])

            async def mock_fetch(**kwargs):
                call_order.append("fetch")
                fetch_kwargs.update(kwargs)

            async def mock_branch_exists(name):
                call_order.append("branch_exists")
                return False

            async def mock_create_branch(name, base):
                call_order.append("create_branch")

            git.fetch = mock_fetch
            git.branch_exists = mock_branch_exists
            git.create_branch = mock_create_branch
            MockGit.return_value = git

            await TaskGitService.create_task_branch(mock_task_no_worktree)

        assert call_order == ["branch_exists", "fetch", "create_branch"]
        assert fetch_kwargs == {"remote": "origin", "branch": "main", "timeout": 10.0}

    @pytest.mark.asyncio
    async def test_fetch_failure_still_creates_branch(self, mock_task_no_worktree):
        """Branch is still created when fetch fails."""
        mock_task_no_worktree.base_branch = "origin/main"

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.list_remotes = AsyncMock(return_value=["origin"])
            git.fetch = AsyncMock(side_effect=ShellCommandExecutionError("network error"))
            git.branch_exists = AsyncMock(return_value=False)
            git.create_branch = AsyncMock()
            MockGit.return_value = git

            result = await TaskGitService.create_task_branch(mock_task_no_worktree)

        assert result == "feature/test-branch"
        git.create_branch.assert_called_once_with("feature/test-branch", "origin/main")

    @pytest.mark.asyncio
    async def test_fetch_timeout_still_creates_branch(self, mock_task_no_worktree):
        """Branch is still created when fetch times out."""
        mock_task_no_worktree.base_branch = "origin/main"

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.list_remotes = AsyncMock(return_value=["origin"])
            git.fetch = AsyncMock(side_effect=ShellCommandTimeoutError("timed out"))
            git.branch_exists = AsyncMock(return_value=False)
            git.create_branch = AsyncMock()
            MockGit.return_value = git

            result = await TaskGitService.create_task_branch(mock_task_no_worktree)

        assert result == "feature/test-branch"
        git.create_branch.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_branch_skips_fetch(self, mock_task_no_worktree):
        """Fetch is not called when branch already exists."""

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.list_remotes = AsyncMock(return_value=["origin"])
            git.fetch = AsyncMock()
            git.branch_exists = AsyncMock(return_value=True)
            MockGit.return_value = git

            await TaskGitService.create_task_branch(mock_task_no_worktree)

        git.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_fetch_for_local_base_branch(self, mock_task_no_worktree):
        """Fetch is skipped when base_branch has no remote prefix."""
        mock_task_no_worktree.base_branch = "main"

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.list_remotes = AsyncMock(return_value=["origin"])
            git.fetch = AsyncMock()
            git.branch_exists = AsyncMock(return_value=False)
            git.create_branch = AsyncMock()
            MockGit.return_value = git

            await TaskGitService.create_task_branch(mock_task_no_worktree)

        git.fetch.assert_not_called()
        git.create_branch.assert_called_once_with("feature/test-branch", "main")


class TestVerifyTaskBranchExists:
    """Tests for verify_task_branch_exists."""

    @pytest.mark.asyncio
    async def test_raises_when_branch_missing(self, mock_task_no_worktree):
        """TaskBranchNotFoundException is raised when the branch does not exist."""

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.branch_exists = AsyncMock(return_value=False)
            MockGit.return_value = git

            with pytest.raises(TaskBranchNotFoundException) as exc_info:
                await TaskGitService.verify_task_branch_exists(mock_task_no_worktree)

        assert exc_info.value.branch_name == "feature/test-branch"
        assert exc_info.value.task_id == mock_task_no_worktree.id

    @pytest.mark.asyncio
    async def test_passes_when_branch_exists(self, mock_task_no_worktree):
        """No exception is raised when the branch exists."""

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.branch_exists = AsyncMock(return_value=True)
            MockGit.return_value = git

            await TaskGitService.verify_task_branch_exists(mock_task_no_worktree)  # should not raise


class TestGetTaskGitStatusFetch:
    """Tests for remote fetch behaviour in get_task_git_status."""

    @pytest.fixture
    def comparison(self):
        return BranchComparison(ahead=2, behind=1, can_merge=True, has_conflicts=False)

    @pytest.mark.asyncio
    async def test_fetches_before_comparison(self, mock_task_no_worktree, comparison):
        """Fetch is called before branch comparison and remote_fetch_failed is False on success."""
        mock_task_no_worktree.base_branch = "origin/main"

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.has_uncommitted_changes = AsyncMock(return_value=True)
            git.get_current_branch = AsyncMock(return_value="main")
            git.branch_exists = AsyncMock(return_value=True)
            git.list_remotes = AsyncMock(return_value=["origin"])
            git.fetch = AsyncMock()
            git.get_branch_comparison = AsyncMock(return_value=comparison)
            MockGit.return_value = git

            status = await TaskGitService.get_task_git_status(mock_task_no_worktree)

        assert status.remote_fetch_failed is False
        git.fetch.assert_called_once_with(remote="origin", branch="main", timeout=10.0)

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_stale_flag(self, mock_task_no_worktree, comparison):
        """remote_fetch_failed is True when fetch fails, status still returned."""
        mock_task_no_worktree.base_branch = "origin/main"

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.has_uncommitted_changes = AsyncMock(return_value=True)
            git.get_current_branch = AsyncMock(return_value="main")
            git.branch_exists = AsyncMock(return_value=True)
            git.list_remotes = AsyncMock(return_value=["origin"])
            git.fetch = AsyncMock(side_effect=ShellCommandExecutionError("network error"))
            git.get_branch_comparison = AsyncMock(return_value=comparison)
            MockGit.return_value = git

            status = await TaskGitService.get_task_git_status(mock_task_no_worktree)

        assert status.remote_fetch_failed is True
        assert status.commits_ahead == 2
        assert status.commits_behind == 1

    @pytest.mark.asyncio
    async def test_no_fetch_when_branch_missing(self, mock_task_no_worktree):
        """Fetch is not called when branch doesn't exist."""

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.has_uncommitted_changes = AsyncMock(return_value=True)
            git.get_current_branch = AsyncMock(return_value="main")
            git.branch_exists = AsyncMock(return_value=False)
            git.list_remotes = AsyncMock(return_value=["origin"])
            git.fetch = AsyncMock()
            MockGit.return_value = git

            status = await TaskGitService.get_task_git_status(mock_task_no_worktree)

        assert status.remote_fetch_failed is False
        git.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_fetch_for_local_base_branch(self, mock_task_no_worktree, comparison):
        """remote_fetch_failed is False and fetch is skipped for local base branches."""
        mock_task_no_worktree.base_branch = "main"

        with patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit:
            git = Mock()
            git.has_uncommitted_changes = AsyncMock(return_value=False)
            git.get_current_branch = AsyncMock(return_value="main")
            git.branch_exists = AsyncMock(return_value=True)
            git.list_remotes = AsyncMock(return_value=["origin"])
            git.fetch = AsyncMock()
            git.get_branch_comparison = AsyncMock(return_value=comparison)
            MockGit.return_value = git

            status = await TaskGitService.get_task_git_status(mock_task_no_worktree)

        assert status.remote_fetch_failed is False
        git.fetch.assert_not_called()
