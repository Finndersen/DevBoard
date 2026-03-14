"""Tests for merge strategies and TaskGitService.merge_task_feature_branch()."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.db.models.codebase import MergeMethod
from devboard.db.models.task import Task
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.types import BranchComparison, BranchReleaseResult
from devboard.services.task_git.merge_strategy import MergeCommitMerge, RebaseMerge, SquashMerge
from devboard.services.task_git.service import TaskGitService
from devboard.services.task_git.types import MergeOutcome, MergeResult


@pytest.fixture
def mock_task():
    task = MagicMock(spec=Task)
    task.id = 1
    task.branch_name = "feature/my-task"
    task.base_branch = "main"
    task.title = "My Task"
    task.codebase = MagicMock()
    task.codebase.merge_method = MergeMethod.SQUASH
    task.codebase.local_path = "/repo"
    return task


@pytest.fixture
def mock_git():
    git = MagicMock(spec=GitRepoIntegration)
    git.stash = AsyncMock(return_value=None)
    git.stash_pop = AsyncMock()
    git.get_checked_out_location = AsyncMock(return_value=None)
    git.has_uncommitted_changes = AsyncMock(return_value=False)
    git.get_changed_file_paths = AsyncMock(return_value=[])
    git.get_current_branch = AsyncMock(return_value="main")
    git.checkout_branch = AsyncMock()
    git.merge_squash = AsyncMock(return_value="abc123")
    git.fast_forward_merge = AsyncMock(return_value="abc123")
    git.merge_branch = AsyncMock(return_value="abc123")
    git.delete_branch = AsyncMock()
    git.is_branch_pushed = AsyncMock(return_value=False)
    git.push_delete_branch = AsyncMock()
    git.rebase_branch = AsyncMock()
    git.get_branch_comparison = AsyncMock(
        return_value=BranchComparison(ahead=1, behind=0, has_conflicts=False, can_merge=True)
    )
    git.release_branch_from_worktree = AsyncMock(return_value=BranchReleaseResult(worktree_path=None, stash_sha=None))
    return git


@pytest.fixture
def mock_worktree_git():
    git = MagicMock(spec=GitRepoIntegration)
    git.stash = AsyncMock(return_value=None)
    git.stash_pop = AsyncMock()
    git.merge_squash = AsyncMock(return_value="abc123")
    git.fast_forward_merge = AsyncMock(return_value="abc123")
    git.merge_branch = AsyncMock(return_value="abc123")
    return git


# ── Pre-check tests (in merge_task_feature_branch) ────────────────────────────


@pytest.fixture
def task_git_service():
    return TaskGitService()


@pytest.mark.asyncio
async def test_merge_blocked_when_uncommitted_changes_overlap_with_feature(
    task_git_service, mock_task, mock_git, mock_worktree_git
):
    """merge_task_feature_branch returns ERROR when uncommitted changes overlap with feature branch."""
    mock_git.get_checked_out_location.return_value = "/worktrees/main"
    mock_git.get_changed_file_paths = AsyncMock(return_value=["src/shared.py", "src/feature_only.py"])
    mock_worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/shared.py", "src/local.py"])

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration", return_value=mock_git) as MockGit,
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_worktree_git),
    ):
        MockGit.side_effect = [mock_git, mock_worktree_git]

        result = await task_git_service.merge_task_feature_branch(mock_task)

    assert result == MergeResult(
        outcome=MergeOutcome.ERROR,
        merge_method=MergeMethod.SQUASH,
        message=(
            "Cannot merge: uncommitted changes in '/worktrees/main' overlap with feature branch changes:\n"
            "  - src/shared.py\n"
            "Please commit or stash these files first."
        ),
    )
    # Branch should NOT be released when the check fails (would leave worktree in detached HEAD)
    mock_git.release_branch_from_worktree.assert_not_called()


@pytest.mark.asyncio
async def test_merge_proceeds_when_uncommitted_changes_do_not_overlap(
    task_git_service, mock_task, mock_git, mock_worktree_git
):
    """merge_task_feature_branch proceeds when uncommitted changes don't overlap with feature branch."""
    mock_git.get_checked_out_location.return_value = "/worktrees/main"
    mock_git.get_changed_file_paths = AsyncMock(return_value=["src/feature_only.py"])
    mock_worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/local_only.py"])
    mock_worktree_git.merge_squash = AsyncMock(return_value="abc123")

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit,
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_worktree_git),
    ):
        MockGit.side_effect = [mock_git, mock_worktree_git]

        result = await task_git_service.merge_task_feature_branch(mock_task)

    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_merge_proceeds_when_base_branch_workdir_is_clean(
    task_git_service, mock_task, mock_git, mock_worktree_git
):
    """merge_task_feature_branch proceeds when base branch workdir has no uncommitted changes."""
    mock_git.get_checked_out_location.return_value = "/worktrees/main"
    mock_worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=[])
    mock_worktree_git.merge_squash = AsyncMock(return_value="abc123")

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit,
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_worktree_git),
    ):
        MockGit.side_effect = [mock_git, mock_worktree_git]

        result = await task_git_service.merge_task_feature_branch(mock_task)

    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_merge_proceeds_when_base_branch_not_checked_out(task_git_service, mock_task, mock_git):
    """merge_task_feature_branch proceeds when base branch is not checked out anywhere."""
    mock_git.get_checked_out_location.return_value = None

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration", return_value=mock_git),
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git),
    ):
        result = await task_git_service.merge_task_feature_branch(mock_task)

    assert result.outcome == MergeOutcome.SUCCESS
    mock_git.has_uncommitted_changes.assert_not_called()


@pytest.mark.asyncio
async def test_merge_raises_for_remote_base_branch(task_git_service, mock_task):
    """merge_task_feature_branch raises ValueError when base branch is a remote tracking branch."""
    mock_task.base_branch = "origin/main"

    with pytest.raises(ValueError, match="requires a local base branch"):
        await task_git_service.merge_task_feature_branch(mock_task)


# ── Worktree stash removal tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_squash_merge_no_stash_in_worktree_path(mock_task, mock_git, mock_worktree_git):
    """SquashMerge does NOT call stash on the worktree git when base branch is checked out there."""
    mock_git.get_checked_out_location = AsyncMock(return_value="/worktrees/main")

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_worktree_git):
        result = await SquashMerge().execute(mock_task, mock_git)

    mock_worktree_git.stash.assert_not_called()
    mock_worktree_git.stash_pop.assert_not_called()
    mock_worktree_git.merge_squash.assert_called_once_with(
        source=mock_task.branch_name,
        target=mock_task.base_branch,
        title=mock_task.title,
    )
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_merge_commit_no_stash_in_worktree_path(mock_task, mock_git, mock_worktree_git):
    """MergeCommitMerge does NOT call stash on the worktree git when base branch is checked out there."""
    mock_task.codebase.merge_method = MergeMethod.MERGE_COMMIT
    mock_git.get_checked_out_location = AsyncMock(return_value="/worktrees/main")

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_worktree_git):
        result = await MergeCommitMerge().execute(mock_task, mock_git)

    mock_worktree_git.stash.assert_not_called()
    mock_worktree_git.stash_pop.assert_not_called()
    mock_worktree_git.merge_branch.assert_called_once_with(mock_task.branch_name, mock_task.base_branch, no_ff=True)
    assert result.outcome == MergeOutcome.SUCCESS


# ── Branch restoration tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_squash_merge_does_not_restore_branch_on_success_when_base_not_checked_out(mock_task, mock_git):
    """SquashMerge leaves repo on base branch after successful merge in no-worktree path."""
    mock_git.get_checked_out_location = AsyncMock(return_value=None)
    mock_git.get_current_branch = AsyncMock(return_value=mock_task.branch_name)

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git):
        result = await SquashMerge().execute(mock_task, mock_git)

    mock_git.get_current_branch.assert_called()
    mock_git.checkout_branch.assert_not_called()
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_squash_merge_restores_original_branch_on_failure_when_base_not_checked_out(mock_task, mock_git):
    """SquashMerge restores original branch when merge fails in no-worktree path."""
    mock_git.get_checked_out_location = AsyncMock(return_value=None)
    mock_git.get_current_branch = AsyncMock(return_value="my-feature")
    mock_git.merge_squash = AsyncMock(side_effect=Exception("merge failed"))

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git):
        with pytest.raises(Exception, match="merge failed"):
            await SquashMerge().execute(mock_task, mock_git)

    mock_git.checkout_branch.assert_called_with("my-feature")


@pytest.mark.asyncio
async def test_rebase_merge_does_not_restore_branch_on_success_when_base_not_checked_out(mock_task, mock_git):
    """RebaseMerge leaves repo on base branch after successful merge in no-worktree path."""
    mock_task.codebase.merge_method = MergeMethod.REBASE
    mock_git.get_checked_out_location = AsyncMock(return_value=None)
    mock_git.get_current_branch = AsyncMock(return_value=mock_task.branch_name)

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git):
        result = await RebaseMerge().execute(mock_task, mock_git)

    mock_git.get_current_branch.assert_called()
    mock_git.checkout_branch.assert_not_called()
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_rebase_merge_restores_original_branch_on_failure_when_base_not_checked_out(mock_task, mock_git):
    """RebaseMerge restores original branch when fast-forward merge fails in no-worktree path."""
    mock_task.codebase.merge_method = MergeMethod.REBASE
    mock_git.get_checked_out_location = AsyncMock(return_value=None)
    mock_git.get_current_branch = AsyncMock(return_value="my-feature")
    mock_git.fast_forward_merge = AsyncMock(side_effect=Exception("ff merge failed"))

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git):
        with pytest.raises(Exception, match="ff merge failed"):
            await RebaseMerge().execute(mock_task, mock_git)

    mock_git.checkout_branch.assert_called_with("my-feature")


@pytest.mark.asyncio
async def test_squash_merge_does_not_restore_branch_on_failure_when_feature_branch_was_current(mock_task, mock_git):
    """SquashMerge does not restore branch when merge fails and current branch was the feature branch."""
    mock_git.get_checked_out_location = AsyncMock(return_value=None)
    mock_git.get_current_branch = AsyncMock(return_value=mock_task.branch_name)
    mock_git.merge_squash = AsyncMock(side_effect=Exception("merge failed"))

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git):
        with pytest.raises(Exception, match="merge failed"):
            await SquashMerge().execute(mock_task, mock_git)

    mock_git.checkout_branch.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_merge_does_not_restore_branch_on_failure_when_feature_branch_was_current(mock_task, mock_git):
    """RebaseMerge does not restore branch when ff merge fails and current branch was the feature branch."""
    mock_task.codebase.merge_method = MergeMethod.REBASE
    mock_git.get_checked_out_location = AsyncMock(return_value=None)
    mock_git.get_current_branch = AsyncMock(return_value=mock_task.branch_name)
    mock_git.fast_forward_merge = AsyncMock(side_effect=Exception("ff merge failed"))

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git):
        with pytest.raises(Exception, match="ff merge failed"):
            await RebaseMerge().execute(mock_task, mock_git)

    mock_git.checkout_branch.assert_not_called()
