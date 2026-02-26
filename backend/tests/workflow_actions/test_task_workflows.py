from unittest.mock import AsyncMock, Mock

import pytest

from devboard.integrations.types import FileDiff, GitLogEntry, StructuredDiff
from devboard.workflow_actions.task_workflows import _get_task_changes_prompt_context


@pytest.fixture
def mock_task():
    task = Mock()
    task.id = 1
    task.branch_name = "feature/test"
    task.base_branch = "main"
    return task


@pytest.fixture
def mock_task_git_service():
    service = Mock()
    service.get_task_commit_metadata = AsyncMock()
    service.get_task_uncommitted_changes = AsyncMock()
    return service


class TestGetTaskChangesPromptContext:
    @pytest.mark.asyncio
    async def test_no_worktree_slot_returns_fallback(self, mock_task_git_service, mock_task):
        mock_task_git_service.worktree_slot_repo.get_last_used_slot_for_task.return_value = None

        result = await _get_task_changes_prompt_context(mock_task_git_service, mock_task)

        assert "Unable to determine branch state" in result
        assert "no worktree slot found" in result
        mock_task_git_service.get_task_commit_metadata.assert_not_called()
        mock_task_git_service.get_task_uncommitted_changes.assert_not_called()

    @pytest.mark.asyncio
    async def test_worktree_with_uncommitted_changes(self, mock_task_git_service, mock_task):
        mock_task_git_service.worktree_slot_repo.get_last_used_slot_for_task.return_value = Mock(path="/tmp/slot")
        mock_task_git_service.get_task_commit_metadata.return_value = [
            GitLogEntry(hash="abc1234", author="Test", date="2024-01-01", subject="First commit"),
            GitLogEntry(hash="def5678", author="Test", date="2024-01-02", subject="Second commit"),
        ]
        mock_task_git_service.get_task_uncommitted_changes.return_value = StructuredDiff(
            files=[
                FileDiff(file_path="src/new.py", diff_content="", additions=10, deletions=0, is_new_file=True),
            ],
            additions=10,
            deletions=0,
        )

        result = await _get_task_changes_prompt_context(mock_task_git_service, mock_task)

        assert "Commits on task branch" in result
        assert "abc1234: First commit" in result
        assert "def5678: Second commit" in result
        assert "Uncommitted changes" in result
        assert "src/new.py (+10/-0) (new)" in result

    @pytest.mark.asyncio
    async def test_worktree_with_no_uncommitted_changes(self, mock_task_git_service, mock_task):
        mock_task_git_service.worktree_slot_repo.get_last_used_slot_for_task.return_value = Mock(path="/tmp/slot")
        mock_task_git_service.get_task_commit_metadata.return_value = [
            GitLogEntry(hash="abc1234", author="Test", date="2024-01-01", subject="Implement feature"),
        ]
        mock_task_git_service.get_task_uncommitted_changes.return_value = StructuredDiff(
            files=[],
            additions=0,
            deletions=0,
        )

        result = await _get_task_changes_prompt_context(mock_task_git_service, mock_task)

        assert "Commits on task branch" in result
        assert "abc1234: Implement feature" in result
        assert "No uncommitted changes" in result
        assert "Uncommitted changes:" not in result

    @pytest.mark.asyncio
    async def test_worktree_with_no_commits(self, mock_task_git_service, mock_task):
        mock_task_git_service.worktree_slot_repo.get_last_used_slot_for_task.return_value = Mock(path="/tmp/slot")
        mock_task_git_service.get_task_commit_metadata.return_value = []
        mock_task_git_service.get_task_uncommitted_changes.return_value = StructuredDiff(
            files=[
                FileDiff(file_path="src/foo.py", diff_content="", additions=5, deletions=2),
            ],
            additions=5,
            deletions=2,
        )

        result = await _get_task_changes_prompt_context(mock_task_git_service, mock_task)

        assert "No commits on task branch yet" in result
        assert "Uncommitted changes" in result
        assert "src/foo.py (+5/-2)" in result
