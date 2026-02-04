"""Tests for rebase tools."""

from unittest.mock import AsyncMock, patch

import pytest

from devboard.agents.tools.rebase_tools import (
    _format_commit_details,
    _get_commits_for_conflicted_files,
)
from devboard.integrations.types import GitLogEntry
from devboard.services.task_git_service import BaseBranchChanges


class TestFormatCommitDetails:
    """Tests for _format_commit_details helper function."""

    def test_format_empty_commits(self):
        """Test formatting empty list returns empty string."""
        result = _format_commit_details([])
        assert result == ""

    def test_format_single_commit_subject_only(self):
        """Test formatting single commit with subject only."""
        commits = [
            GitLogEntry(
                hash="abc123def456",
                author="John Doe",
                date="2024-01-15",
                subject="Fix critical bug",
            )
        ]
        result = _format_commit_details(commits)
        assert result == "  - **abc123d**: Fix critical bug"

    def test_format_single_commit_with_body(self):
        """Test formatting single commit with subject and body."""
        commits = [
            GitLogEntry(
                hash="abc123def456",
                author="John Doe",
                date="2024-01-15",
                subject="Fix critical bug",
                body="This fixes issue #123.\n\nDetails here.",
            )
        ]
        result = _format_commit_details(commits)

        lines = result.split("\n")
        assert len(lines) == 4
        assert lines[0] == "  - **abc123d**: Fix critical bug"
        assert lines[1] == "    This fixes issue #123."
        assert lines[2] == "    "
        assert lines[3] == "    Details here."

    def test_format_multiple_commits(self):
        """Test formatting multiple commits."""
        commits = [
            GitLogEntry(
                hash="abc1234567890",
                author="John",
                date="2024-01-15",
                subject="First commit",
            ),
            GitLogEntry(
                hash="def4567890123",
                author="Jane",
                date="2024-01-16",
                subject="Second commit",
                body="With a body",
            ),
        ]
        result = _format_commit_details(commits)

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == "  - **abc1234**: First commit"
        assert lines[1] == "  - **def4567**: Second commit"
        assert lines[2] == "    With a body"


class TestGetCommitsForConflictedFiles:
    """Tests for _get_commits_for_conflicted_files helper function."""

    @pytest.mark.asyncio
    async def test_returns_filtered_commits(self):
        """Test that commits are filtered by conflicted files."""
        base_branch_changes = BaseBranchChanges(
            commits=[],
            files_changed=["file1.py", "file2.py", "file3.py"],
            additions=100,
            deletions=50,
            fork_point="fork123",
            base_head="head456",
        )
        conflicted_files = ["file1.py", "file3.py"]

        expected_commits = [
            GitLogEntry(
                hash="abc123",
                author="John",
                date="2024-01-15",
                subject="Update file1",
            ),
        ]

        with patch("devboard.agents.tools.rebase_tools.GitRepoIntegration") as MockGit:
            mock_git = MockGit.return_value
            mock_git.get_commits_in_range = AsyncMock(return_value=expected_commits)

            result = await _get_commits_for_conflicted_files(
                base_branch_changes,
                conflicted_files,
                "/repo/path",
            )

        assert result == expected_commits
        mock_git.get_commits_in_range.assert_called_once_with(
            "fork123",
            "head456",
            file_paths=["file1.py", "file3.py"],
        )

    @pytest.mark.asyncio
    async def test_passes_correct_repo_path(self):
        """Test that GitRepoIntegration is initialized with correct path."""
        base_branch_changes = BaseBranchChanges(
            commits=[],
            files_changed=[],
            additions=0,
            deletions=0,
            fork_point="fork123",
            base_head="head456",
        )

        with patch("devboard.agents.tools.rebase_tools.GitRepoIntegration") as MockGit:
            mock_git = MockGit.return_value
            mock_git.get_commits_in_range = AsyncMock(return_value=[])

            await _get_commits_for_conflicted_files(
                base_branch_changes,
                ["file.py"],
                "/custom/repo/path",
            )

        MockGit.assert_called_once_with("/custom/repo/path")
