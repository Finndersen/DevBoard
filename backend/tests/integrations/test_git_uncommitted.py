"""Tests for Git integration uncommitted file methods."""

from unittest.mock import AsyncMock, patch

import pytest

from devboard.integrations.git import GitRepoIntegration


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary directory with .git folder."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    return repo_path


class TestGetUncommittedFilePaths:
    """Tests for get_uncommitted_file_paths method."""

    @pytest.mark.asyncio
    async def test_no_changes(self, temp_git_repo):
        """Returns empty list when no uncommitted changes exist."""
        git = GitRepoIntegration(temp_git_repo)

        with patch.object(git, "_run_git_command", new_callable=AsyncMock, return_value=""):
            result = await git.get_uncommitted_file_paths()

        assert result == []

    @pytest.mark.asyncio
    async def test_unstaged_only(self, temp_git_repo):
        """Returns unstaged file paths."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run(args, raise_on_error=True, timeout=30.0):
            if "--cached" in args:
                return ""
            return "src/main.py\nsrc/utils.py"

        with patch.object(git, "_run_git_command", side_effect=mock_run):
            result = await git.get_uncommitted_file_paths()

        assert result == ["src/main.py", "src/utils.py"]

    @pytest.mark.asyncio
    async def test_staged_only(self, temp_git_repo):
        """Returns staged file paths."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run(args, raise_on_error=True, timeout=30.0):
            if "--cached" in args:
                return "src/new_file.py"
            return ""

        with patch.object(git, "_run_git_command", side_effect=mock_run):
            result = await git.get_uncommitted_file_paths()

        assert result == ["src/new_file.py"]

    @pytest.mark.asyncio
    async def test_mixed_staged_and_unstaged(self, temp_git_repo):
        """Returns deduplicated paths from both staged and unstaged changes."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run(args, raise_on_error=True, timeout=30.0):
            if "--cached" in args:
                return "src/main.py\nsrc/staged_only.py"
            return "src/main.py\nsrc/unstaged_only.py"

        with patch.object(git, "_run_git_command", side_effect=mock_run):
            result = await git.get_uncommitted_file_paths()

        assert result == ["src/main.py", "src/staged_only.py", "src/unstaged_only.py"]

    @pytest.mark.asyncio
    async def test_deduplicates_files(self, temp_git_repo):
        """Files appearing in both staged and unstaged are deduplicated."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run(args, raise_on_error=True, timeout=30.0):
            if "--cached" in args:
                return "shared.py"
            return "shared.py"

        with patch.object(git, "_run_git_command", side_effect=mock_run):
            result = await git.get_uncommitted_file_paths()

        assert result == ["shared.py"]


class TestGetChangedFilePaths:
    """Tests for get_changed_file_paths method."""

    @pytest.mark.asyncio
    async def test_returns_changed_files(self, temp_git_repo):
        """Returns file paths changed between two commits."""
        git = GitRepoIntegration(temp_git_repo)

        with patch.object(git, "_run_git_command", new_callable=AsyncMock, return_value="file_a.py\nfile_b.py"):
            result = await git.get_changed_file_paths("abc123", "def456")

        assert result == ["file_a.py", "file_b.py"]

    @pytest.mark.asyncio
    async def test_no_changes(self, temp_git_repo):
        """Returns empty list when no files changed."""
        git = GitRepoIntegration(temp_git_repo)

        with patch.object(git, "_run_git_command", new_callable=AsyncMock, return_value=""):
            result = await git.get_changed_file_paths("abc123", "abc123")

        assert result == []
