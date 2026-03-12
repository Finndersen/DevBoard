from unittest.mock import AsyncMock, Mock

import pytest

from devboard.db.models.codebase import MergeMethod
from devboard.integrations.types import FileDiff, GitLogEntry, StructuredDiff
from devboard.workflow_actions.task_workflows import ApproveAndMergeAction, _get_task_changes_prompt_context


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
        mock_task.last_used_worktree_slot = None

        result = await _get_task_changes_prompt_context(mock_task_git_service, mock_task)

        assert "Unable to determine branch state" in result
        assert "no worktree slot found" in result
        mock_task_git_service.get_task_commit_metadata.assert_not_called()
        mock_task_git_service.get_task_uncommitted_changes.assert_not_called()

    @pytest.mark.asyncio
    async def test_worktree_with_uncommitted_changes(self, mock_task_git_service, mock_task):
        mock_task.last_used_worktree_slot = Mock(path="/tmp/slot")
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
        mock_task.last_used_worktree_slot = Mock(path="/tmp/slot")
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
        mock_task.last_used_worktree_slot = Mock(path="/tmp/slot")
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


class TestApproveAndMergePrompt:
    CHANGES_CONTEXT = "```\nNo commits on task branch yet.\n\nUncommitted changes:\n  src/foo.py (+5/-2)\n```"

    @pytest.mark.parametrize(
        "merge_method,expected_phrases",
        [
            (MergeMethod.SQUASH, ["single commit", "squashed"]),
            (MergeMethod.REBASE, ["atomic commits", "replayed"]),
            (MergeMethod.MERGE_COMMIT, ["appropriate commit(s)", "preserved"]),
        ],
    )
    def test_commit_instruction_by_merge_method(self, merge_method: MergeMethod, expected_phrases: list[str]):
        prompt = ApproveAndMergeAction._build_prompt(merge_method, self.CHANGES_CONTEXT)

        for phrase in expected_phrases:
            assert phrase in prompt

    @pytest.mark.parametrize("merge_method", list(MergeMethod))
    def test_always_includes_complete_task_tool(self, merge_method: MergeMethod):
        prompt = ApproveAndMergeAction._build_prompt(merge_method, self.CHANGES_CONTEXT)

        assert "complete_task_with_local_merge" in prompt

    def test_unknown_merge_method_uses_fallback(self):
        prompt = ApproveAndMergeAction._build_prompt("unknown_method", self.CHANGES_CONTEXT)

        assert "appropriate commit(s)" in prompt
        assert "clear commit messages" in prompt
        assert "complete_task_with_local_merge" in prompt
