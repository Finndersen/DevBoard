"""Tests for task completion tools."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry, Tool

from devboard.agents.tools.task_completion_tools import (
    create_complete_task_with_local_merge_tool,
    create_merge_pr_and_complete_task_tool,
)
from devboard.db.models import Task
from devboard.db.models.codebase import MergeMethod
from devboard.integrations.github import GitHubIntegration, GitHubPR, GitHubRepository, PRStatus, PullRequestMergeResult
from devboard.services.task_git_service import MergeOutcome, MergeResult
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_task():
    """Create a mock Task."""
    task = Mock(spec=Task)
    task.id = 1
    task.get_current_workspace_dir = Mock(return_value="/tmp/test-workspace")
    return task


@pytest.fixture
def mock_task_service():
    """Create a mock TaskService."""
    service = Mock(spec=TaskService)
    service.complete_task_with_local_merge = AsyncMock()
    return service


class TestCreateCompleteTaskWithLocalMergeTool:
    """Tests for create_complete_task_with_local_merge_tool."""

    def test_tool_creation(self, mock_task, mock_task_service):
        """Tool is created with correct name."""
        tool = create_complete_task_with_local_merge_tool(mock_task, mock_task_service)

        assert isinstance(tool, Tool)
        assert tool.name == "complete_task_with_local_merge"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_uncommitted_changes_raises_model_retry(self, mock_task, mock_task_service):
        """Raises ModelRetry when workspace has uncommitted changes."""
        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=True)
            mock_git_class.return_value = mock_git

            tool = create_complete_task_with_local_merge_tool(mock_task, mock_task_service)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "Cannot merge" in str(exc_info.value)
            assert "uncommitted changes" in str(exc_info.value)
            mock_task_service.complete_task_with_local_merge.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_merge(self, mock_task, mock_task_service):
        """Returns success message when merge completes."""
        merge_result = MergeResult(
            outcome=MergeOutcome.SUCCESS,
            merge_method=MergeMethod.SQUASH,
            message="Squash merged feature branch into main",
            merge_commit="abc123",
        )
        mock_task_service.complete_task_with_local_merge.return_value = merge_result

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_complete_task_with_local_merge_tool(mock_task, mock_task_service)
            result = await tool.function(change_summary="Test change summary content")

            assert "Task completed successfully" in result
            assert "Squash merged feature branch into main" in result
            assert "abc123" in result
            mock_task_service.complete_task_with_local_merge.assert_called_once_with(
                mock_task, "Test change summary content"
            )

    @pytest.mark.asyncio
    async def test_successful_merge_without_commit_hash(self, mock_task, mock_task_service):
        """Returns success message without commit hash when not provided."""
        merge_result = MergeResult(
            outcome=MergeOutcome.SUCCESS,
            merge_method=MergeMethod.REBASE,
            message="Rebased feature branch onto main",
            merge_commit=None,
        )
        mock_task_service.complete_task_with_local_merge.return_value = merge_result

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_complete_task_with_local_merge_tool(mock_task, mock_task_service)
            result = await tool.function(change_summary="Test summary")

            assert "Task completed successfully" in result
            assert "Rebased feature branch onto main" in result
            assert "Merge commit:" not in result

    @pytest.mark.asyncio
    async def test_merge_failure_raises_model_retry(self, mock_task, mock_task_service):
        """Raises ModelRetry when merge fails."""
        mock_task_service.complete_task_with_local_merge.side_effect = ValueError(
            "Merge failed (conflict): Conflicts detected in src/main.py"
        )

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_complete_task_with_local_merge_tool(mock_task, mock_task_service)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "Merge failed" in str(exc_info.value)
            assert "conflict" in str(exc_info.value)


@pytest.fixture
def mock_task_with_pr():
    """Create a mock Task with PR configuration."""
    task = Mock(spec=Task)
    task.id = 1
    task.github_pr_number = 42
    task.get_current_workspace_dir = Mock(return_value="/tmp/test-workspace")
    # Set up codebase with merge_method and repository_url
    task.codebase = Mock()
    task.codebase.merge_method = MergeMethod.SQUASH.value
    task.codebase.repository_url = "https://github.com/test/repo"
    return task


@pytest.fixture
def mock_github_pr():
    """Create a mock GitHubPR with default mergeable status."""
    pr = Mock(spec=GitHubPR)
    pr.merge = AsyncMock()
    # Default to a mergeable PR status
    pr.get_status = AsyncMock(
        return_value=PRStatus(
            pr_number=42,
            state="open",
            merged=False,
            mergeable=True,
            mergeable_state="clean",
            ci_status="success",
            ci_checks=[],
        )
    )
    return pr


@pytest.fixture
def mock_github_repo(mock_github_pr):
    """Create a mock GitHubRepository that returns mock_github_pr."""
    repo = Mock(spec=GitHubRepository)
    repo.get_pull_request = AsyncMock(return_value=mock_github_pr)
    return repo


@pytest.fixture
def mock_github_integration(mock_github_repo):
    """Create a mock GitHubIntegration that returns mock_github_repo."""
    integration = Mock(spec=GitHubIntegration)
    integration.get_repository_from_url = AsyncMock(return_value=mock_github_repo)
    return integration


class TestCreateMergePRAndCompleteTaskTool:
    """Tests for create_merge_pr_and_complete_task_tool."""

    def test_tool_creation(self, mock_task_with_pr, mock_task_service, mock_github_integration):
        """Tool is created with correct name."""
        tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)

        assert isinstance(tool, Tool)
        assert tool.name == "merge_pr_and_complete_task"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_no_pr_configured_raises_model_retry(self, mock_task_service, mock_github_integration):
        """Raises ModelRetry when task has no PR configured."""
        task = Mock(spec=Task)
        task.id = 1
        task.github_pr_number = None

        tool = create_merge_pr_and_complete_task_tool(task, mock_task_service, mock_github_integration)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(change_summary="Test summary")

        assert "no PR configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_uncommitted_changes_raises_model_retry(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Raises ModelRetry when workspace has uncommitted changes."""
        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=True)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "uncommitted changes" in str(exc_info.value)
            mock_github_pr.merge.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_merge(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Returns success message when PR merge completes."""
        mock_github_pr.merge.return_value = PullRequestMergeResult(
            merged=True, sha="abc123def456", message="Pull Request successfully merged"
        )
        mock_task_service.complete_pr_task = AsyncMock()

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)
            result = await tool.function(change_summary="Test change summary")

            assert "Task completed successfully" in result
            assert "abc123def456" in result
            mock_github_pr.merge.assert_called_once_with(merge_method=MergeMethod.SQUASH)
            mock_task_service.complete_pr_task.assert_called_once_with(mock_task_with_pr, "Test change summary")

    @pytest.mark.asyncio
    async def test_github_merge_failure_raises_model_retry(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Raises ModelRetry when GitHub merge API fails."""
        mock_github_pr.merge.side_effect = Exception("Merge conflict detected")

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "Failed to merge PR" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_merge_not_successful_raises_model_retry(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Raises ModelRetry when GitHub merge returns merged=False."""
        mock_github_pr.merge.return_value = PullRequestMergeResult(
            merged=False, sha=None, message="Branch protection rules violated"
        )

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "PR merge was not successful" in str(exc_info.value)
            assert "Branch protection rules violated" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_task_completion_failure_raises_model_retry(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Raises ModelRetry when task completion fails."""
        mock_github_pr.merge.return_value = PullRequestMergeResult(merged=True, sha="abc123", message="Merged")
        mock_task_service.complete_pr_task = AsyncMock(side_effect=ValueError("Task has invalid status for completion"))

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "Task has invalid status" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_already_merged_pr_completes_task(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Completes task when PR was already merged on GitHub."""
        mock_github_pr.get_status.return_value = PRStatus(
            pr_number=42,
            state="closed",
            merged=True,
            mergeable=None,
            mergeable_state=None,
            ci_status=None,
            ci_checks=[],
        )
        mock_task_service.complete_pr_task = AsyncMock()

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)
            result = await tool.function(change_summary="Test summary")

            assert "Task completed successfully" in result
            assert "already merged on GitHub" in result
            mock_github_pr.merge.assert_not_called()
            mock_task_service.complete_pr_task.assert_called_once_with(mock_task_with_pr, "Test summary")

    @pytest.mark.asyncio
    async def test_closed_pr_raises_model_retry(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Raises ModelRetry when PR is closed but not merged."""
        mock_github_pr.get_status.return_value = PRStatus(
            pr_number=42,
            state="closed",
            merged=False,
            mergeable=None,
            mergeable_state=None,
            ci_status=None,
            ci_checks=[],
        )

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "PR is not open" in str(exc_info.value)
            mock_github_pr.merge.assert_not_called()

    @pytest.mark.asyncio
    async def test_pr_with_conflicts_raises_model_retry(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Raises ModelRetry when PR has merge conflicts."""
        mock_github_pr.get_status.return_value = PRStatus(
            pr_number=42,
            state="open",
            merged=False,
            mergeable=False,
            mergeable_state="dirty",
            ci_status="success",
            ci_checks=[],
        )

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "merge conflicts" in str(exc_info.value)
            mock_github_pr.merge.assert_not_called()

    @pytest.mark.asyncio
    async def test_pr_blocked_by_branch_protection_raises_model_retry(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Raises ModelRetry when PR is blocked by branch protection."""
        mock_github_pr.get_status.return_value = PRStatus(
            pr_number=42,
            state="open",
            merged=False,
            mergeable=False,
            mergeable_state="blocked",
            ci_status="success",
            ci_checks=[],
        )

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "branch protection" in str(exc_info.value)
            mock_github_pr.merge.assert_not_called()

    @pytest.mark.asyncio
    async def test_pr_with_failing_ci_raises_model_retry(
        self, mock_task_with_pr, mock_task_service, mock_github_integration, mock_github_pr
    ):
        """Raises ModelRetry when PR has failing CI checks."""
        mock_github_pr.get_status.return_value = PRStatus(
            pr_number=42,
            state="open",
            merged=False,
            mergeable=False,
            mergeable_state="unstable",
            ci_status="failure",
            ci_checks=[],
        )

        with patch("devboard.agents.tools.task_completion_tools.GitRepoIntegration") as mock_git_class:
            mock_git = Mock()
            mock_git.has_uncommitted_changes = AsyncMock(return_value=False)
            mock_git_class.return_value = mock_git

            tool = create_merge_pr_and_complete_task_tool(mock_task_with_pr, mock_task_service, mock_github_integration)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(change_summary="Test summary")

            assert "failing CI" in str(exc_info.value)
            mock_github_pr.merge.assert_not_called()
