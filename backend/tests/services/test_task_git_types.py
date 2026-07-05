"""Tests for task_git types — BaseBranchChanges.format_summary."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.db.models import Task
from devboard.db.models.worktree_slot import WorktreeSlot
from devboard.integrations.types import FileDiff, GitLogEntry
from devboard.services.task_git.rebase_coordinator import TaskRebaseCoordinator
from devboard.services.task_git.types import BaseBranchChanges, RebaseOutcome


def _make_file(path: str, additions: int = 5, deletions: int = 2) -> FileDiff:
    return FileDiff(file_path=path, diff_content="", additions=additions, deletions=deletions)


def _make_commit(hash_: str, subject: str) -> GitLogEntry:
    return GitLogEntry(hash=hash_, author="Dev", date="2024-01-01", subject=subject)


@pytest.fixture
def base_changes() -> BaseBranchChanges:
    return BaseBranchChanges(
        commits=[_make_commit("aabbccddeeff", "Update shared module")],
        files_changed=[
            _make_file("src/shared.py"),
            _make_file("src/base_only.py"),
            _make_file("src/another_base.py"),
        ],
        additions=12,
        deletions=6,
        fork_point="fork123",
        base_head="base456",
    )


class TestFormatSummaryNoOverlap:
    """format_summary with no task file overlap renders single-section output."""

    def test_single_section_no_headers_when_no_task_files(self, base_changes: BaseBranchChanges):
        output = base_changes.format_summary("main")

        assert "**Files changed:**" in output
        assert "src/shared.py" in output
        assert "potential conflicts" not in output
        assert "Other base branch files" not in output

    def test_single_section_when_no_overlap(self, base_changes: BaseBranchChanges):
        output = base_changes.format_summary("main", task_file_paths={"src/task_only.py"})

        assert "**Files changed:**" in output
        assert "potential conflicts" not in output
        assert "src/shared.py" in output


class TestFormatSummaryWithOverlap:
    """format_summary with overlapping files renders two-section output."""

    def test_overlap_section_first_then_other(self, base_changes: BaseBranchChanges):
        output = base_changes.format_summary("main", task_file_paths={"src/shared.py"})

        conflict_pos = output.index("potential conflicts")
        other_pos = output.index("Other base branch files")
        assert conflict_pos < other_pos

    def test_overlapping_file_appears_in_conflict_section(self, base_changes: BaseBranchChanges):
        output = base_changes.format_summary("main", task_file_paths={"src/shared.py"})

        assert "**Files also changed in your task branch (potential conflicts):**" in output
        # shared.py should appear before "Other base branch files"
        conflict_pos = output.index("src/shared.py")
        other_header_pos = output.index("Other base branch files")
        assert conflict_pos < other_header_pos

    def test_non_overlapping_files_in_other_section(self, base_changes: BaseBranchChanges):
        output = base_changes.format_summary("main", task_file_paths={"src/shared.py"})

        other_pos = output.index("Other base branch files")
        remaining = output[other_pos:]
        assert "src/base_only.py" in remaining
        assert "src/another_base.py" in remaining

    def test_all_files_overlapping_omits_other_section(self, base_changes: BaseBranchChanges):
        all_paths = {"src/shared.py", "src/base_only.py", "src/another_base.py"}
        output = base_changes.format_summary("main", task_file_paths=all_paths)

        assert "**Files also changed in your task branch (potential conflicts):**" in output
        assert "Other base branch files" not in output


class TestStartRebasePopulatesTaskFilesChanged:
    """_start_rebase computes and stores task branch changed files."""

    @pytest.fixture
    def mock_task(self):
        task = MagicMock(spec=Task)
        task.id = 42
        task.branch_name = "feature/my-task"
        task.base_branch = "main"
        return task

    @pytest.fixture
    def mock_slot(self):
        slot = MagicMock(spec=WorktreeSlot)
        slot.path = "/repo/.worktrees/slot-1"
        return slot

    @pytest.mark.asyncio
    async def test_task_files_changed_populated_on_success(self, mock_task, mock_slot):
        """task_files_changed is set on success result from task branch diff."""
        mock_task.last_used_worktree_slot = mock_slot

        with patch("devboard.services.task_git.rebase_coordinator.GitRepoIntegration") as mock_git_cls:
            mock_git = mock_git_cls.return_value
            mock_git.is_rebase_in_progress.return_value = False
            mock_git.stash_push = AsyncMock(return_value=None)
            mock_git.get_fork_point = AsyncMock(return_value="fork123")
            mock_git.get_changed_file_paths = AsyncMock(return_value=["src/feature.py", "src/shared.py"])
            mock_git.list_remotes = AsyncMock(return_value=[])
            mock_git.get_branch_head = AsyncMock(return_value="fork123")  # no base changes
            mock_git.rebase_branch = AsyncMock(return_value="newhead")
            mock_git.find_stash_by_message = AsyncMock(return_value=None)

            result = await TaskRebaseCoordinator.rebase_task_branch(mock_task)

        assert result.outcome == RebaseOutcome.SUCCESS
        assert result.task_files_changed == ["src/feature.py", "src/shared.py"]
        mock_git.get_changed_file_paths.assert_called_once_with("fork123", "feature/my-task")

    @pytest.mark.asyncio
    async def test_task_files_changed_empty_when_no_fork_point(self, mock_task, mock_slot):
        """task_files_changed is empty list when fork_point is None."""
        mock_task.last_used_worktree_slot = mock_slot

        with patch("devboard.services.task_git.rebase_coordinator.GitRepoIntegration") as mock_git_cls:
            mock_git = mock_git_cls.return_value
            mock_git.is_rebase_in_progress.return_value = False
            mock_git.stash_push = AsyncMock(return_value=None)
            mock_git.get_fork_point = AsyncMock(return_value=None)
            mock_git.list_remotes = AsyncMock(return_value=[])
            mock_git.get_branch_head = AsyncMock(return_value=None)
            mock_git.rebase_branch = AsyncMock(return_value="newhead")
            mock_git.find_stash_by_message = AsyncMock(return_value=None)

            result = await TaskRebaseCoordinator.rebase_task_branch(mock_task)

        assert result.task_files_changed == []
        mock_git.get_changed_file_paths.assert_not_called()
