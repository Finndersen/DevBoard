"""Tests for GitHub tools - create_pull_request conflict pre-check."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.github_tools import create_get_pr_status_tool, create_github_pr_tool
from devboard.db.models.task import Task
from devboard.integrations.github import GitHubIntegration, GitHubRepository, OpenPullRequest, PullRequest
from devboard.integrations.types import BranchComparison
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_task():
    """Create a mock Task with codebase."""
    task = Mock(spec=Task)
    task.id = 1
    task.branch_name = "feature/test"
    task.base_branch = "main"
    task.codebase = Mock()
    task.codebase.repository_url = "https://github.com/test/repo"
    task.codebase.local_path = "/repo"
    task.get_current_workspace_dir = Mock(return_value="/worktrees/slot-1")
    task.github_pr_number = None
    return task


@pytest.fixture
def mock_github_integration():
    """Create a mock GitHubIntegration."""
    integration = Mock(spec=GitHubIntegration)
    repo = Mock(spec=GitHubRepository)
    repo.find_pull_request_for_branch = AsyncMock(return_value=None)
    pr = Mock(spec=PullRequest)
    pr.number = 42
    repo.create_pull_request = AsyncMock(return_value=pr)
    integration.get_repository_from_url = AsyncMock(return_value=repo)
    return integration


@pytest.fixture
def mock_task_service():
    """Create a mock TaskService."""
    service = Mock(spec=TaskService)
    service.transition_to_pr_open = Mock()
    return service


class TestCreatePullRequestConflictPreCheck:
    """Tests for conflict pre-check in create_pull_request tool."""

    @pytest.mark.asyncio
    async def test_conflicts_raises_model_retry(self, mock_task, mock_github_integration, mock_task_service):
        """Raises ModelRetry when branch has conflicts with base."""
        mock_task.base_branch = "origin/main"
        comparison_with_conflicts = BranchComparison(ahead=3, behind=2, can_merge=False, has_conflicts=True)

        with patch("devboard.agents.tools.github_tools.GitRepoIntegration") as MockGit:
            workspace_git = Mock()
            workspace_git.has_uncommitted_changes = AsyncMock(return_value=False)

            main_git = Mock()
            main_git.list_remotes = AsyncMock(return_value=["origin"])
            main_git.fetch = AsyncMock()
            main_git.get_branch_comparison = AsyncMock(return_value=comparison_with_conflicts)

            def git_side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return workspace_git
                return main_git

            MockGit.side_effect = git_side_effect

            tool = create_github_pr_tool(mock_task, mock_github_integration, mock_task_service)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(title="Test PR", body="Test body")

            assert "merge conflicts detected" in str(exc_info.value)
            assert "rebase_task_branch" in str(exc_info.value)
            main_git.fetch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_conflicts_proceeds(self, mock_task, mock_github_integration, mock_task_service):
        """Proceeds with PR creation when no conflicts."""
        mock_task.base_branch = "origin/main"
        comparison_no_conflicts = BranchComparison(ahead=3, behind=0, can_merge=True, has_conflicts=False)

        with patch("devboard.agents.tools.github_tools.GitRepoIntegration") as MockGit:
            workspace_git = Mock()
            workspace_git.has_uncommitted_changes = AsyncMock(return_value=False)
            workspace_git.push_branch = AsyncMock()

            main_git = Mock()
            main_git.list_remotes = AsyncMock(return_value=["origin"])
            main_git.fetch = AsyncMock()
            main_git.get_branch_comparison = AsyncMock(return_value=comparison_no_conflicts)

            def git_side_effect(path):
                if str(path) == "/worktrees/slot-1":
                    return workspace_git
                return main_git

            MockGit.side_effect = git_side_effect

            tool = create_github_pr_tool(mock_task, mock_github_integration, mock_task_service)
            result = await tool.function(title="Test PR", body="Test body")

            assert "Successfully created PR #42" in result
            mock_task_service.transition_to_pr_open.assert_called_once()
            main_git.fetch.assert_awaited_once()


class TestGetPRStatusTool:
    """Tests for the get_pr_status tool created by create_get_pr_status_tool."""

    @pytest.mark.asyncio
    async def test_returns_formatted_status_for_valid_pr(self):
        """Returns formatted PR status string for a valid PR."""
        task = Mock(spec=Task)
        task.github_pr_number = 42
        task.codebase = Mock()
        task.codebase.repository_url = "https://github.com/owner/repo"

        github_integration = Mock(spec=GitHubIntegration)
        github_integration.parse_repo_url = Mock(return_value=("owner", "repo"))
        github_integration.get_pull_request_status = AsyncMock(
            return_value=OpenPullRequest(
                number=42,
                title="Fix bug",
                html_url="https://github.com/owner/repo/pull/42",
                mergeable_state="MERGEABLE",
                repo_full_name="owner/repo",
                updated_at=datetime(2024, 1, 1),
                review_decision="APPROVED",
                ci_status="SUCCESS",
                comment_count=3,
                state="OPEN",
            )
        )

        tool = create_get_pr_status_tool(task, github_integration)
        result = await tool.function()

        assert "PR #42" in result
        assert "OPEN" in result
        assert "MERGEABLE" in result
        assert "APPROVED" in result
        assert "SUCCESS" in result
        assert "3" in result
        assert "get_pr_feedback" in result

    @pytest.mark.asyncio
    async def test_raises_model_retry_when_no_pr_number(self):
        """Raises ModelRetry when task has no github_pr_number."""
        task = Mock(spec=Task)
        task.github_pr_number = None
        task.codebase = Mock()
        task.codebase.repository_url = "https://github.com/owner/repo"

        github_integration = Mock(spec=GitHubIntegration)

        tool = create_get_pr_status_tool(task, github_integration)

        with pytest.raises(ModelRetry):
            await tool.function()

    @pytest.mark.asyncio
    async def test_raises_model_retry_when_no_repository_url(self):
        """Raises ModelRetry when task codebase has no repository_url."""
        task = Mock(spec=Task)
        task.github_pr_number = 42
        task.codebase = Mock()
        task.codebase.repository_url = None

        github_integration = Mock(spec=GitHubIntegration)

        tool = create_get_pr_status_tool(task, github_integration)

        with pytest.raises(ModelRetry):
            await tool.function()

    @pytest.mark.asyncio
    async def test_raises_model_retry_on_api_error(self):
        """Raises ModelRetry with appropriate message when GitHub API call fails."""
        task = Mock(spec=Task)
        task.github_pr_number = 42
        task.codebase = Mock()
        task.codebase.repository_url = "https://github.com/owner/repo"

        github_integration = Mock(spec=GitHubIntegration)
        github_integration.parse_repo_url = Mock(return_value=("owner", "repo"))
        github_integration.get_pull_request_status = AsyncMock(side_effect=Exception("API error"))

        tool = create_get_pr_status_tool(task, github_integration)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function()

        assert "Failed to fetch PR status" in str(exc_info.value)
