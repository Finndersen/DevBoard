"""Tests for merge strategies and TaskGitService.merge_task_feature_branch()."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.db.models.codebase import MergeMethod
from devboard.db.models.task import Task
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.types import BranchComparison, BranchReleaseResult, GitLogEntry
from devboard.services.task_git.merge_strategy import MergeCommitMerge, RebaseMerge, SquashMerge
from devboard.services.task_git.service import BaseWorkdirOverlapError, TaskGitService
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
def mock_commits():
    """Two mock commits to trigger squash logic."""
    return [
        MagicMock(spec=GitLogEntry, subject="feat: first change"),
        MagicMock(spec=GitLogEntry, subject="feat: second change"),
    ]


@pytest.fixture
def mock_git(mock_commits):
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
    git.get_merge_base = AsyncMock(return_value="merge_base_sha")
    git.get_commits_in_range = AsyncMock(return_value=mock_commits)
    git.soft_reset = AsyncMock()
    git.commit = AsyncMock(return_value="squashed_sha")
    git.run_git_command = AsyncMock(return_value="abc123")
    return git


@pytest.fixture
def mock_worktree_git():
    git = MagicMock(spec=GitRepoIntegration)
    git.stash = AsyncMock(return_value=None)
    git.stash_pop = AsyncMock()
    git.merge_squash = AsyncMock(return_value="abc123")
    git.fast_forward_merge = AsyncMock(return_value="abc123")
    git.merge_branch = AsyncMock(return_value="abc123")
    git.soft_reset = AsyncMock()
    git.commit = AsyncMock(return_value="squashed_sha")
    git.rebase_onto = AsyncMock(return_value="rebased_sha")
    return git


# ── Pre-check tests (in merge_task_feature_branch) ────────────────────────────


@pytest.mark.asyncio
async def test_merge_blocked_when_uncommitted_changes_overlap_with_feature(mock_task, mock_git, mock_worktree_git):
    """merge_task_feature_branch raises BaseWorkdirOverlapError when uncommitted changes overlap with feature branch."""
    mock_git.get_checked_out_location.return_value = "/worktrees/main"
    mock_git.get_changed_file_paths = AsyncMock(return_value=["src/shared.py", "src/feature_only.py"])
    mock_worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/shared.py", "src/local.py"])

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration", return_value=mock_git) as MockGit,
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_worktree_git),
    ):
        MockGit.side_effect = [mock_git, mock_worktree_git]

        with pytest.raises(BaseWorkdirOverlapError) as exc_info:
            await TaskGitService.merge_task_feature_branch(mock_task)

    assert exc_info.value.checkout_path == "/worktrees/main"
    assert exc_info.value.overlapping_files == ["src/shared.py"]
    assert "Cannot merge" in str(exc_info.value)
    assert "src/shared.py" in str(exc_info.value)
    # Branch should NOT be released when the check fails (would leave worktree in detached HEAD)
    mock_git.release_branch_from_worktree.assert_not_called()


@pytest.mark.asyncio
async def test_merge_proceeds_when_uncommitted_changes_do_not_overlap(mock_task, mock_git, mock_worktree_git):
    """merge_task_feature_branch proceeds when uncommitted changes don't overlap with feature branch."""
    mock_git.get_checked_out_location = AsyncMock(
        side_effect=lambda branch: "/worktrees/main" if branch == mock_task.base_branch else None
    )
    mock_git.get_changed_file_paths = AsyncMock(return_value=["src/feature_only.py"])
    mock_worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=["src/local_only.py"])
    mock_worktree_git.merge_squash = AsyncMock(return_value="abc123")

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit,
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_worktree_git),
    ):
        MockGit.side_effect = [mock_git, mock_worktree_git]

        result = await TaskGitService.merge_task_feature_branch(mock_task)

    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_merge_proceeds_when_base_branch_workdir_is_clean(mock_task, mock_git, mock_worktree_git):
    """merge_task_feature_branch proceeds when base branch workdir has no uncommitted changes."""
    mock_git.get_checked_out_location = AsyncMock(
        side_effect=lambda branch: "/worktrees/main" if branch == mock_task.base_branch else None
    )
    mock_worktree_git.get_uncommitted_file_paths = AsyncMock(return_value=[])
    mock_worktree_git.merge_squash = AsyncMock(return_value="abc123")

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit,
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_worktree_git),
    ):
        MockGit.side_effect = [mock_git, mock_worktree_git]

        result = await TaskGitService.merge_task_feature_branch(mock_task)

    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_merge_proceeds_when_base_branch_not_checked_out(mock_task, mock_git):
    """merge_task_feature_branch proceeds when base branch is not checked out anywhere."""
    mock_git.get_checked_out_location.return_value = None

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration", return_value=mock_git),
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git),
    ):
        result = await TaskGitService.merge_task_feature_branch(mock_task)

    assert result.outcome == MergeOutcome.SUCCESS
    mock_git.has_uncommitted_changes.assert_not_called()


@pytest.mark.asyncio
async def test_merge_blocked_when_feature_worktree_has_uncommitted_changes(mock_task, mock_git):
    """merge_task_feature_branch returns ERROR when feature branch worktree has uncommitted changes."""
    mock_git.repo_path = "/repo"
    mock_git.get_checked_out_location = AsyncMock(
        side_effect=lambda branch: "/worktrees/feature" if branch == mock_task.branch_name else None
    )

    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.has_uncommitted_changes = AsyncMock(return_value=True)

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit,
    ):
        MockGit.side_effect = [mock_git, mock_feature_git]

        result = await TaskGitService.merge_task_feature_branch(mock_task)

    assert result == MergeResult(
        outcome=MergeOutcome.ERROR,
        merge_method=MergeMethod.SQUASH,
        message="Cannot merge: task branch has uncommitted changes in '/worktrees/feature'. Commit or discard all changes before merging.",
    )
    mock_git.release_branch_from_worktree.assert_not_called()


@pytest.mark.asyncio
async def test_merge_proceeds_when_feature_worktree_is_clean(mock_task, mock_git):
    """merge_task_feature_branch proceeds when feature worktree has no uncommitted changes."""
    mock_git.repo_path = "/repo"
    mock_git.get_checked_out_location = AsyncMock(
        side_effect=lambda branch: "/worktrees/feature" if branch == mock_task.branch_name else None
    )

    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.has_uncommitted_changes = AsyncMock(return_value=False)

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration") as MockGit,
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git),
    ):
        MockGit.side_effect = [mock_git, mock_feature_git, mock_git]

        result = await TaskGitService.merge_task_feature_branch(mock_task)

    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_merge_checks_uncommitted_changes_when_branch_checked_out_in_main_repo(mock_task, mock_git):
    """merge_task_feature_branch checks for uncommitted changes even when branch is in the main repo.

    Previously this check was skipped for the main repo path, which could lead to merging a
    branch with uncommitted changes. Now we always check regardless of location.
    """
    mock_git.repo_path = "/repo"
    # Feature branch is checked out at the main repo path
    mock_git.get_checked_out_location = AsyncMock(return_value="/repo")
    # No uncommitted changes
    mock_git.has_uncommitted_changes = AsyncMock(return_value=False)

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration", return_value=mock_git),
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git),
    ):
        result = await TaskGitService.merge_task_feature_branch(mock_task)

    assert result.outcome == MergeOutcome.SUCCESS
    # has_uncommitted_changes IS now called even for the main repo path
    mock_git.has_uncommitted_changes.assert_called()


@pytest.mark.asyncio
async def test_merge_blocks_when_branch_in_main_repo_has_uncommitted_changes(mock_task, mock_git):
    """merge_task_feature_branch returns ERROR when the feature branch in main repo has uncommitted changes."""
    mock_git.repo_path = "/repo"
    mock_git.get_checked_out_location = AsyncMock(return_value="/repo")
    # Uncommitted changes present
    mock_git.has_uncommitted_changes = AsyncMock(return_value=True)

    with (
        patch("devboard.services.task_git.service.GitRepoIntegration", return_value=mock_git),
        patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git),
    ):
        result = await TaskGitService.merge_task_feature_branch(mock_task)

    assert result.outcome == MergeOutcome.ERROR
    assert "uncommitted changes" in result.message.lower()


# ── Worktree stash removal tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_squash_merge_squashes_multiple_commits_via_soft_reset_in_feature_worktree(
    mock_task, mock_git, mock_commits
):
    """SquashMerge squashes multiple commits via soft_reset+commit on the feature worktree."""
    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.soft_reset = AsyncMock()
    mock_feature_git.commit = AsyncMock(return_value="squashed_sha")
    mock_feature_git.rebase_onto = AsyncMock()

    mock_base_git = MagicMock(spec=GitRepoIntegration)
    mock_base_git.fast_forward_merge = AsyncMock(return_value="ff_sha")

    mock_git.get_checked_out_location = AsyncMock(return_value="/worktrees/main")
    mock_git.get_commits_in_range = AsyncMock(return_value=mock_commits)

    def git_factory(path):
        return mock_feature_git if path == "/worktrees/feature" else mock_base_git

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", side_effect=git_factory):
        result = await SquashMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    mock_feature_git.soft_reset.assert_called_once_with("merge_base_sha")
    mock_feature_git.commit.assert_called_once()
    commit_args = mock_feature_git.commit.call_args
    assert commit_args.kwargs.get("no_verify") is True or commit_args.args[1] is True
    mock_feature_git.rebase_onto.assert_called_once_with(mock_task.base_branch)
    mock_base_git.fast_forward_merge.assert_called_once_with(source=mock_task.branch_name, target=mock_task.base_branch)
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_squash_merge_skips_soft_reset_for_single_commit(mock_task, mock_git):
    """SquashMerge skips soft_reset when the feature branch already has a single commit."""
    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.soft_reset = AsyncMock()
    mock_feature_git.commit = AsyncMock(return_value="sha")
    mock_feature_git.rebase_onto = AsyncMock()

    mock_base_git = MagicMock(spec=GitRepoIntegration)
    mock_base_git.fast_forward_merge = AsyncMock(return_value="ff_sha")

    mock_git.get_checked_out_location = AsyncMock(return_value="/worktrees/main")
    # Single commit — squash step is a no-op
    single_commit = MagicMock(spec=GitLogEntry, subject="feat: only commit")
    mock_git.get_commits_in_range = AsyncMock(return_value=[single_commit])

    def git_factory(path):
        return mock_feature_git if path == "/worktrees/feature" else mock_base_git

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", side_effect=git_factory):
        result = await SquashMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    mock_feature_git.soft_reset.assert_not_called()
    mock_feature_git.commit.assert_not_called()
    mock_feature_git.rebase_onto.assert_called_once_with(mock_task.base_branch)
    mock_base_git.fast_forward_merge.assert_called_once_with(source=mock_task.branch_name, target=mock_task.base_branch)
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_squash_merge_no_stash_on_worktree_gits(mock_task, mock_git, mock_worktree_git):
    """SquashMerge does NOT call stash on any worktree git — only on the main git object."""
    mock_git.get_checked_out_location = AsyncMock(return_value="/worktrees/main")

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_worktree_git):
        result = await SquashMerge().execute(mock_task, mock_git)

    mock_worktree_git.stash.assert_not_called()
    mock_worktree_git.stash_pop.assert_not_called()
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
async def test_squash_merge_restores_original_branch_on_ff_failure_when_base_not_checked_out(mock_task, mock_git):
    """SquashMerge restores original branch when fast-forward fails and base is not in a worktree."""
    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.soft_reset = AsyncMock()
    mock_feature_git.commit = AsyncMock(return_value="squashed_sha")
    mock_feature_git.rebase_onto = AsyncMock()

    mock_git.get_current_branch = AsyncMock(return_value="some-other-branch")
    mock_git.fast_forward_merge = AsyncMock(side_effect=Exception("ff failed"))
    # Base branch is not checked out anywhere
    mock_git.get_checked_out_location = AsyncMock(return_value=None)

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_feature_git):
        with pytest.raises(Exception, match="ff failed"):
            await SquashMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    mock_git.checkout_branch.assert_called_with("some-other-branch")


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
async def test_squash_merge_does_not_restore_branch_when_ff_fails_and_feature_was_current(mock_task, mock_git):
    """SquashMerge does not restore branch when ff fails and current branch is the feature branch.

    With feature_worktree_path set, the strategy operates in the worktree without touching main repo HEAD.
    When the ff merge then fails (base not in worktree, main repo is used), and current branch
    was already the task branch, no restore is needed.
    """
    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.soft_reset = AsyncMock()
    mock_feature_git.commit = AsyncMock(return_value="squashed_sha")
    mock_feature_git.rebase_onto = AsyncMock()

    mock_git.get_current_branch = AsyncMock(return_value=mock_task.branch_name)
    mock_git.fast_forward_merge = AsyncMock(side_effect=Exception("ff failed"))
    # Base branch is not checked out anywhere
    mock_git.get_checked_out_location = AsyncMock(return_value=None)

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_feature_git):
        with pytest.raises(Exception, match="ff failed"):
            await SquashMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    mock_git.checkout_branch.assert_not_called()


@pytest.mark.asyncio
async def test_squash_merge_rebases_feature_onto_base_when_not_in_worktree(mock_task, mock_git):
    """SquashMerge calls rebase_branch on repo_git when feature branch is not in a worktree."""
    mock_git.get_checked_out_location = AsyncMock(return_value=None)

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git):
        result = await SquashMerge().execute(mock_task, mock_git)

    mock_git.rebase_branch.assert_called_once_with(mock_task.branch_name, mock_task.base_branch)
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_squash_merge_rebases_feature_worktree_onto_base(mock_task, mock_git):
    """SquashMerge calls rebase_onto on the feature worktree git when feature_worktree_path is provided."""
    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.soft_reset = AsyncMock()
    mock_feature_git.commit = AsyncMock(return_value="squashed_sha")
    mock_feature_git.rebase_onto = AsyncMock()

    mock_base_git = MagicMock(spec=GitRepoIntegration)
    mock_base_git.fast_forward_merge = AsyncMock(return_value="ff_sha")

    mock_git.get_checked_out_location = AsyncMock(return_value="/worktrees/main")

    def git_factory(path):
        return mock_feature_git if path == "/worktrees/feature" else mock_base_git

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", side_effect=git_factory):
        result = await SquashMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    mock_feature_git.rebase_onto.assert_called_once_with(mock_task.base_branch)
    mock_git.rebase_branch.assert_not_called()
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_squash_merge_remote_base_fetches_squashes_rebases_and_pushes(mock_task, mock_git, mock_commits):
    """SquashMerge for remote base: squashes on feature worktree, fetches, rebases, then pushes."""
    mock_task.base_branch = "origin/main"

    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.soft_reset = AsyncMock()
    mock_feature_git.commit = AsyncMock(return_value="squashed_sha")
    mock_feature_git.rebase_onto = AsyncMock(return_value="rebased_sha")

    mock_git.get_commits_in_range = AsyncMock(return_value=mock_commits)
    mock_git.run_git_command = AsyncMock(return_value="pushed_sha")

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_feature_git):
        result = await SquashMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    mock_feature_git.soft_reset.assert_called_once_with("merge_base_sha")
    mock_feature_git.commit.assert_called_once()
    # fetch, then rebase in feature worktree
    mock_git.run_git_command.assert_any_call(["fetch", "origin", "main"])
    mock_feature_git.rebase_onto.assert_called_once_with("origin/main")
    # push feature branch to remote base
    mock_git.run_git_command.assert_any_call(["push", "origin", f"{mock_task.branch_name}:main"], timeout=60.0)
    assert result.outcome == MergeOutcome.SUCCESS


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


# ── feature_worktree_path tests (Fix 1: operate in worktree, not main repo) ────


@pytest.mark.asyncio
async def test_squash_merge_uses_feature_worktree_path_for_squash_and_rebase(mock_task, mock_git, mock_commits):
    """SquashMerge uses feature_worktree_path to squash and rebase when branch not currently checked out."""
    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.soft_reset = AsyncMock()
    mock_feature_git.commit = AsyncMock(return_value="squashed_sha")
    mock_feature_git.rebase_onto = AsyncMock()

    mock_base_git = MagicMock(spec=GitRepoIntegration)
    mock_base_git.fast_forward_merge = AsyncMock(return_value="ff_sha")

    # Branch not currently checked out anywhere (was released from worktree)
    mock_git.get_checked_out_location = AsyncMock(
        side_effect=lambda branch: "/worktrees/main" if branch == mock_task.base_branch else None
    )
    mock_git.get_commits_in_range = AsyncMock(return_value=mock_commits)

    def git_factory(path):
        return mock_feature_git if path == "/worktrees/feature" else mock_base_git

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", side_effect=git_factory):
        result = await SquashMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    # Should re-checkout branch in the feature worktree and squash there
    mock_feature_git.checkout_branch.assert_called_with(mock_task.branch_name)
    mock_feature_git.soft_reset.assert_called_once_with("merge_base_sha")
    mock_feature_git.commit.assert_called_once()
    # Should rebase within the worktree (not the main repo)
    mock_feature_git.rebase_onto.assert_called_with(mock_task.base_branch)
    mock_git.rebase_branch.assert_not_called()
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_squash_merge_uses_feature_worktree_path_for_rebase_single_commit(mock_task, mock_git):
    """SquashMerge uses feature_worktree_path for rebase even for single-commit (no-squash) case."""
    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.rebase_onto = AsyncMock()

    mock_base_git = MagicMock(spec=GitRepoIntegration)
    mock_base_git.fast_forward_merge = AsyncMock(return_value="ff_sha")

    # Single commit — squash is a no-op
    single_commit = MagicMock(spec=GitLogEntry, subject="feat: only commit")
    mock_git.get_commits_in_range = AsyncMock(return_value=[single_commit])

    # Branch not currently checked out anywhere
    mock_git.get_checked_out_location = AsyncMock(
        side_effect=lambda branch: "/worktrees/main" if branch == mock_task.base_branch else None
    )

    def git_factory(path):
        return mock_feature_git if path == "/worktrees/feature" else mock_base_git

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", side_effect=git_factory):
        result = await SquashMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    # No squash, but rebase should use worktree
    mock_feature_git.soft_reset.assert_not_called()
    mock_feature_git.checkout_branch.assert_called_with(mock_task.branch_name)
    mock_feature_git.rebase_onto.assert_called_once_with(mock_task.base_branch)
    mock_git.rebase_branch.assert_not_called()
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_rebase_merge_uses_feature_worktree_path(mock_task, mock_git):
    """RebaseMerge uses feature_worktree_path to rebase when branch not currently checked out."""
    mock_task.codebase.merge_method = MergeMethod.REBASE
    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.rebase_onto = AsyncMock()

    mock_base_git = MagicMock(spec=GitRepoIntegration)
    mock_base_git.fast_forward_merge = AsyncMock(return_value="ff_sha")

    # Branch not currently checked out anywhere (was released)
    mock_git.get_checked_out_location = AsyncMock(
        side_effect=lambda branch: "/worktrees/main" if branch == mock_task.base_branch else None
    )

    def git_factory(path):
        return mock_feature_git if path == "/worktrees/feature" else mock_base_git

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", side_effect=git_factory):
        result = await RebaseMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    # Should re-checkout branch in feature worktree and use rebase_onto there
    mock_feature_git.checkout_branch.assert_called_with(mock_task.branch_name)
    mock_feature_git.rebase_onto.assert_called_once_with(mock_task.base_branch)
    mock_git.rebase_branch.assert_not_called()
    assert result.outcome == MergeOutcome.SUCCESS


# ── Regression tests: HEAD-leak bug (Fix 2: main repo HEAD restored before delete) ─


@pytest.mark.asyncio
async def test_squash_merge_restores_main_repo_head_before_branch_delete_when_no_worktree(mock_task, mock_git):
    """SquashMerge restores main repo HEAD after rebase so delete_branch succeeds.

    Regression test for the bug where rebase_branch left the main repo on the task branch,
    causing 'git branch -D' to fail with 'used by worktree'.
    """
    # Simulate: main repo is currently on base branch, no feature worktree
    call_count = 0

    async def get_current_branch_side_effect():
        nonlocal call_count
        call_count += 1
        # After rebase, git would put HEAD on task.branch_name; simulate that on 2nd call
        if call_count == 1:
            return mock_task.base_branch  # before rebase
        return mock_task.branch_name  # after rebase (the bug condition)

    mock_git.get_checked_out_location = AsyncMock(return_value=None)
    mock_git.get_current_branch = AsyncMock(side_effect=get_current_branch_side_effect)

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git):
        result = await SquashMerge().execute(mock_task, mock_git)

    # Main repo HEAD should have been restored to base branch so delete_branch can succeed
    mock_git.checkout_branch.assert_any_call(mock_task.base_branch)
    mock_git.delete_branch.assert_called_once_with(mock_task.branch_name, force=True)
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_rebase_merge_restores_main_repo_head_before_branch_delete_when_no_worktree(mock_task, mock_git):
    """RebaseMerge restores main repo HEAD after rebase so delete_branch succeeds.

    Regression test for the bug where rebase_branch left the main repo on the task branch,
    causing 'git branch -D' to fail with 'used by worktree'.
    """
    mock_task.codebase.merge_method = MergeMethod.REBASE
    call_count = 0

    async def get_current_branch_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_task.base_branch  # before rebase
        return mock_task.branch_name  # after rebase (the bug condition)

    mock_git.get_checked_out_location = AsyncMock(return_value=None)
    mock_git.get_current_branch = AsyncMock(side_effect=get_current_branch_side_effect)

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", return_value=mock_git):
        result = await RebaseMerge().execute(mock_task, mock_git)

    # Main repo HEAD should have been restored to base branch so delete_branch can succeed
    mock_git.checkout_branch.assert_any_call(mock_task.base_branch)
    mock_git.delete_branch.assert_called_once_with(mock_task.branch_name, force=True)
    assert result.outcome == MergeOutcome.SUCCESS


# ── Regression tests: worktree-holds-branch bug (Fix: detach before delete) ─


@pytest.mark.asyncio
async def test_squash_merge_detaches_feature_worktree_before_branch_delete(mock_task, mock_git):
    """SquashMerge detaches the feature worktree before delete_branch when worktree was used.

    Regression test for the bug where checkout_branch inside _squash_feature_branch_commits /
    _squash_to_local_base re-attached the branch to the feature worktree, causing
    'git branch -D' to fail with 'cannot delete branch used by worktree'.
    """
    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.soft_reset = AsyncMock()
    mock_feature_git.commit = AsyncMock()
    mock_feature_git.rebase_onto = AsyncMock()
    mock_feature_git.switch_detach = AsyncMock()

    mock_git.get_checked_out_location = AsyncMock(return_value=None)

    parent = MagicMock()
    parent.attach_mock(mock_feature_git.switch_detach, "switch_detach")
    parent.attach_mock(mock_git.delete_branch, "delete_branch")

    def git_factory(path):
        return mock_feature_git if path == "/worktrees/feature" else MagicMock(spec=GitRepoIntegration)

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", side_effect=git_factory):
        result = await SquashMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    mock_feature_git.switch_detach.assert_called_once()
    mock_git.delete_branch.assert_called_once_with(mock_task.branch_name, force=True)

    # switch_detach must come before delete_branch in the call sequence
    call_names = [c[0] for c in parent.mock_calls]
    assert call_names.index("switch_detach") < call_names.index("delete_branch")
    assert result.outcome == MergeOutcome.SUCCESS


@pytest.mark.asyncio
async def test_rebase_merge_detaches_feature_worktree_before_branch_delete(mock_task, mock_git):
    """RebaseMerge detaches the feature worktree before delete_branch when worktree was used.

    Regression test for the bug where checkout_branch inside RebaseMerge.execute re-attached
    the branch to the feature worktree, causing 'git branch -D' to fail with
    'cannot delete branch used by worktree'.
    """
    mock_task.codebase.merge_method = MergeMethod.REBASE

    mock_feature_git = MagicMock(spec=GitRepoIntegration)
    mock_feature_git.checkout_branch = AsyncMock()
    mock_feature_git.rebase_onto = AsyncMock()
    mock_feature_git.switch_detach = AsyncMock()

    mock_base_git = MagicMock(spec=GitRepoIntegration)
    mock_base_git.fast_forward_merge = AsyncMock(return_value="ff_sha")

    mock_git.get_checked_out_location = AsyncMock(
        side_effect=lambda branch: "/worktrees/main" if branch == mock_task.base_branch else None
    )

    parent = MagicMock()
    parent.attach_mock(mock_feature_git.switch_detach, "switch_detach")
    parent.attach_mock(mock_git.delete_branch, "delete_branch")

    def git_factory(path):
        if path == "/worktrees/feature":
            return mock_feature_git
        return mock_base_git

    with patch("devboard.services.task_git.merge_strategy.GitRepoIntegration", side_effect=git_factory):
        result = await RebaseMerge().execute(mock_task, mock_git, feature_worktree_path="/worktrees/feature")

    mock_feature_git.switch_detach.assert_called_once()
    mock_git.delete_branch.assert_called_once_with(mock_task.branch_name, force=True)

    # switch_detach must come before delete_branch in the call sequence
    call_names = [c[0] for c in parent.mock_calls]
    assert call_names.index("switch_detach") < call_names.index("delete_branch")
    assert result.outcome == MergeOutcome.SUCCESS
