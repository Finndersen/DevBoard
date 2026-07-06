"""Tests for rebase tools."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.rebase_tools import (
    RebaseActionResult,
    _get_commits_for_conflicted_files,
    create_rebase_task_branch_tool,
    execute_rebase_with_result,
)
from devboard.db.models import Task
from devboard.db.models.task import NoWorktreeAllocatedException
from devboard.integrations.types import FileDiff, GitLogEntry
from devboard.services.task_git.types import RebaseOutcome, TaskConfigurationError
from devboard.services.task_git_service import BaseBranchChanges, RebaseResult


class TestGetCommitsForConflictedFiles:
    """Tests for _get_commits_for_conflicted_files helper function."""

    @pytest.mark.asyncio
    async def test_returns_filtered_commits(self):
        """Test that commits are filtered by conflicted files."""
        base_branch_changes = BaseBranchChanges(
            commits=[],
            files_changed=[
                FileDiff(file_path="file1.py", diff_content="", additions=40, deletions=20),
                FileDiff(file_path="file2.py", diff_content="", additions=30, deletions=15),
                FileDiff(file_path="file3.py", diff_content="", additions=30, deletions=15),
            ],
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


class TestExecuteRebaseWithResult:
    """Tests for execute_rebase_with_result() helper function."""

    @pytest.mark.asyncio
    async def test_success_without_base_branch_changes(self):
        """Returns RebaseActionResult(success=True) with new HEAD on clean success."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        rebase_result = RebaseResult(
            outcome=RebaseOutcome.SUCCESS,
            slot_path="/repo/path",
            new_head="abc1234",
        )

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(return_value=rebase_result)

            result = await execute_rebase_with_result(task)

        assert result == RebaseActionResult(
            success=True,
            git_diff_details="Rebase completed successfully. New HEAD: abc1234",
        )

    @pytest.mark.asyncio
    async def test_success_with_base_branch_changes(self):
        """Includes base branch summary in message when base branch changes exist."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        base_changes = Mock(spec=BaseBranchChanges)
        base_changes.format_summary.return_value = "Base branch summary text"

        rebase_result = RebaseResult(
            outcome=RebaseOutcome.SUCCESS,
            slot_path="/repo/path",
            new_head="abc1234",
            base_branch_changes=base_changes,
        )

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(return_value=rebase_result)

            result = await execute_rebase_with_result(task)

        assert result.success is True
        assert "abc1234" in result.git_diff_details
        assert "Base branch summary text" in result.git_diff_details
        assert "Please review these changes" not in result.git_diff_details
        assert result.message == "Please review these changes and note if any are relevant to the current task."
        base_changes.format_summary.assert_called_once_with("main", task_file_paths=set())

    @pytest.mark.asyncio
    async def test_conflict_returns_failure_with_file_list(self):
        """Returns RebaseActionResult(success=False) with conflict details on CONFLICT."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        rebase_result = RebaseResult(
            outcome=RebaseOutcome.CONFLICT,
            slot_path="/repo/path",
            conflicted_files=["src/foo.py", "src/bar.py"],
            has_pending_stash=False,
            base_branch_changes=None,
        )

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(return_value=rebase_result)

            result = await execute_rebase_with_result(task)

        assert result.success is False
        assert "src/foo.py" in result.git_diff_details
        assert "src/bar.py" in result.git_diff_details
        assert "Rebase has conflicts" in result.git_diff_details
        assert result.message is not None
        assert "call this tool again" in result.message

    @pytest.mark.asyncio
    async def test_conflict_includes_stash_note_when_pending(self):
        """Includes stash note in conflict message when uncommitted changes are stashed."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        rebase_result = RebaseResult(
            outcome=RebaseOutcome.CONFLICT,
            slot_path="/repo/path",
            conflicted_files=["file.py"],
            has_pending_stash=True,
            base_branch_changes=None,
        )

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(return_value=rebase_result)

            result = await execute_rebase_with_result(task)

        assert result.success is False
        assert "Uncommitted changes were stashed" in result.git_diff_details

    @pytest.mark.asyncio
    async def test_conflict_includes_relevant_commits(self):
        """Includes base branch commit details for conflicted files when available."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        base_changes = BaseBranchChanges(
            commits=[],
            files_changed=[],
            additions=0,
            deletions=0,
            fork_point="fork123",
            base_head="head456",
        )
        rebase_result = RebaseResult(
            outcome=RebaseOutcome.CONFLICT,
            slot_path="/repo/path",
            conflicted_files=["file.py"],
            has_pending_stash=False,
            base_branch_changes=base_changes,
        )
        relevant_commits = [GitLogEntry(hash="abc1234567", author="Dev", date="2024-01-01", subject="Relevant change")]

        with (
            patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service,
            patch("devboard.agents.tools.rebase_tools._get_commits_for_conflicted_files") as mock_get_commits,
        ):
            mock_service.rebase_task_branch = AsyncMock(return_value=rebase_result)
            mock_get_commits = AsyncMock(return_value=relevant_commits)

            with patch(
                "devboard.agents.tools.rebase_tools._get_commits_for_conflicted_files",
                mock_get_commits,
            ):
                result = await execute_rebase_with_result(task)

        assert result.success is False
        assert "Base branch commits that touched these files" in result.git_diff_details
        assert "Relevant change" in result.git_diff_details

    @pytest.mark.asyncio
    async def test_stash_conflict_returns_failure(self):
        """Returns RebaseActionResult(success=False) with stash conflict details."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        rebase_result = RebaseResult(
            outcome=RebaseOutcome.STASH_CONFLICT,
            slot_path="/repo/path",
            new_head="newhead123",
            conflicted_files=["stash_file.py"],
        )

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(return_value=rebase_result)

            result = await execute_rebase_with_result(task)

        assert result == RebaseActionResult(
            success=False,
            git_diff_details=(
                "Rebase completed successfully (new HEAD: newhead123), but restoring your "
                "uncommitted changes resulted in merge conflicts.\n\n"
                "**Conflicted files:**\n  - stash_file.py"
            ),
            message="Please resolve the conflicts in these files. Once resolved, the rebase operation is complete.",
        )

    @pytest.mark.asyncio
    async def test_raises_task_configuration_error(self):
        """Propagates TaskConfigurationError without wrapping."""
        task = Mock(spec=Task)

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(side_effect=TaskConfigurationError("no branch configured"))

            with pytest.raises(TaskConfigurationError):
                await execute_rebase_with_result(task)

    @pytest.mark.asyncio
    async def test_raises_no_worktree_allocated_exception(self):
        """Propagates NoWorktreeAllocatedException without wrapping."""
        task = Mock(spec=Task)

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(
                side_effect=NoWorktreeAllocatedException("no workspace allocated")
            )

            with pytest.raises(NoWorktreeAllocatedException):
                await execute_rebase_with_result(task)


class TestRebaseTaskBranchToolExceptions:
    """Tests for exception handling in create_rebase_task_branch_tool."""

    @pytest.mark.asyncio
    async def test_task_configuration_error_raises_model_retry(self):
        """Raises ModelRetry when TaskConfigurationError is raised (missing branch name)."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(
                side_effect=TaskConfigurationError("Task 1 has no branch name configured")
            )

            tool = create_rebase_task_branch_tool(task)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function()

            assert "no branch name configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_worktree_allocated_raises_model_retry(self):
        """Raises ModelRetry when NoWorktreeAllocatedException is raised (no workspace)."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(
                side_effect=NoWorktreeAllocatedException("Task 1 has no workspace allocated.")
            )

            tool = create_rebase_task_branch_tool(task)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function()

            assert "no workspace allocated" in str(exc_info.value)


class TestRebaseTaskBranchToolSuccess:
    """Tests for the success return value of create_rebase_task_branch_tool."""

    @pytest.mark.asyncio
    async def test_appends_review_instruction_to_message_when_present(self):
        """Direct tool-call return still includes the review instruction inline with the message."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        base_changes = Mock(spec=BaseBranchChanges)
        base_changes.format_summary.return_value = "Base branch summary text"

        rebase_result = RebaseResult(
            outcome=RebaseOutcome.SUCCESS,
            slot_path="/repo/path",
            new_head="abc1234",
            base_branch_changes=base_changes,
        )

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(return_value=rebase_result)

            tool = create_rebase_task_branch_tool(task)
            result = await tool.function()

        assert "Base branch summary text" in result
        assert "Please review these changes and note if any are relevant to the current task." in result

    @pytest.mark.asyncio
    async def test_no_review_instruction_when_no_base_branch_changes(self):
        """Direct tool-call return has no trailing review instruction when there are no base branch changes."""
        task = Mock(spec=Task)
        task.base_branch = "main"

        rebase_result = RebaseResult(
            outcome=RebaseOutcome.SUCCESS,
            slot_path="/repo/path",
            new_head="abc1234",
        )

        with patch("devboard.agents.tools.rebase_tools.TaskGitService") as mock_service:
            mock_service.rebase_task_branch = AsyncMock(return_value=rebase_result)

            tool = create_rebase_task_branch_tool(task)
            result = await tool.function()

        assert "Please review these changes" not in result
