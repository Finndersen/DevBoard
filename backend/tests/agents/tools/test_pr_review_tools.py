"""Tests for PR review tools."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai import Tool

from devboard.agents.tools import create_get_pr_feedback_tool
from devboard.db.models import Task
from devboard.integrations.github import (
    CommentThread,
    GitHubIntegration,
    GitHubPR,
    GitHubRepository,
    PRFeedback,
    ReviewComment,
    ReviewWithComments,
)


@pytest.fixture
def mock_task():
    """Create a mock Task with PR configuration."""
    task = Mock(spec=Task)
    task.github_pr_number = 42
    task.codebase = Mock()
    task.codebase.repository_url = "https://github.com/test/repo"
    return task


@pytest.fixture
def mock_github_pr():
    """Create a mock GitHubPR with get_feedback as AsyncMock."""
    github_pr = Mock(spec=GitHubPR)
    github_pr.get_feedback = AsyncMock()
    return github_pr


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


class TestCreateGetPrFeedbackTool:
    """Tests for create_get_pr_feedback_tool."""

    def test_tool_creation(self, mock_task, mock_github_integration):
        """Tool is created with correct name."""
        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)

        assert isinstance(tool, Tool)
        assert tool.name == "get_pr_feedback"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_empty_feedback(self, mock_task, mock_github_integration, mock_github_pr):
        """Returns 'No reviews or comments found' message when feedback is empty."""
        mock_github_pr.get_feedback.return_value = PRFeedback(
            reviews=[],
            standalone_threads=[],
        )

        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)
        result = await tool.function()

        assert result == "No reviews or comments found for this PR."
        mock_github_pr.get_feedback.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_formatting(self, mock_task, mock_github_integration, mock_github_pr):
        """Reviews formatted correctly with state, author, body."""
        review = ReviewWithComments(
            id=1,
            author="reviewer1",
            state="CHANGES_REQUESTED",
            body="Please fix the formatting issues.",
            submitted_at=datetime(2024, 1, 15, 10, 30, 0),
            comment_threads=[],
        )
        mock_github_pr.get_feedback.return_value = PRFeedback(
            reviews=[review],
            standalone_threads=[],
        )

        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)
        result = await tool.function()

        assert "# Reviews" in result
        assert "## Review by reviewer1" in result
        assert "**State:** CHANGES_REQUESTED" in result
        assert "**Submitted:** 2024-01-15 10:30:00" in result
        assert "Please fix the formatting issues." in result

    @pytest.mark.asyncio
    async def test_review_without_submitted_at(self, mock_task, mock_github_integration, mock_github_pr):
        """Review without submitted_at date does not include submitted line."""
        review = ReviewWithComments(
            id=1,
            author="reviewer1",
            state="APPROVED",
            body="Looks good!",
            submitted_at=None,
            comment_threads=[],
        )
        mock_github_pr.get_feedback.return_value = PRFeedback(
            reviews=[review],
            standalone_threads=[],
        )

        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)
        result = await tool.function()

        assert "## Review by reviewer1" in result
        assert "**State:** APPROVED" in result
        assert "**Submitted:**" not in result
        assert "Looks good!" in result

    @pytest.mark.asyncio
    async def test_review_with_empty_body(self, mock_task, mock_github_integration, mock_github_pr):
        """Review with empty body does not include body section."""
        review = ReviewWithComments(
            id=1,
            author="reviewer1",
            state="APPROVED",
            body="",
            submitted_at=None,
            comment_threads=[],
        )
        mock_github_pr.get_feedback.return_value = PRFeedback(
            reviews=[review],
            standalone_threads=[],
        )

        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)
        result = await tool.function()

        assert "## Review by reviewer1" in result
        assert "**State:** APPROVED" in result

    @pytest.mark.asyncio
    async def test_thread_with_replies_formatting(self, mock_task, mock_github_integration, mock_github_pr):
        """Replies shown with blockquote syntax."""
        original_comment = ReviewComment(
            id=100,
            author="reviewer1",
            body="This function is too long.",
            path="src/main.py",
            line=42,
            created_at=datetime(2024, 1, 15, 10, 0, 0),
            diff_hunk="@@ -40,6 +40,10 @@\n def main():",
            in_reply_to_id=None,
        )
        reply1 = ReviewComment(
            id=101,
            author="author1",
            body="I will split it into smaller functions.",
            path="src/main.py",
            line=42,
            created_at=datetime(2024, 1, 15, 11, 0, 0),
            diff_hunk=None,
            in_reply_to_id=100,
        )
        reply2 = ReviewComment(
            id=102,
            author="reviewer1",
            body="Thanks!",
            path="src/main.py",
            line=42,
            created_at=datetime(2024, 1, 15, 12, 0, 0),
            diff_hunk=None,
            in_reply_to_id=100,
        )
        thread = CommentThread(
            original=original_comment,
            replies=[reply1, reply2],
        )
        review = ReviewWithComments(
            id=1,
            author="reviewer1",
            state="CHANGES_REQUESTED",
            body="",
            submitted_at=None,
            comment_threads=[thread],
        )
        mock_github_pr.get_feedback.return_value = PRFeedback(
            reviews=[review],
            standalone_threads=[],
        )

        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)
        result = await tool.function()

        # Check original comment formatting
        assert "**reviewer1** at `src/main.py` (line 42):" in result
        assert "This function is too long." in result

        # Check diff hunk is included
        assert "```diff" in result
        assert "@@ -40,6 +40,10 @@" in result

        # Check replies use blockquote syntax
        assert "> **Reply by author1:**" in result
        assert "> I will split it into smaller functions." in result
        assert "> **Reply by reviewer1:**" in result
        assert "> Thanks!" in result

        # Check thread count
        assert "### Code Comments (1 threads)" in result

    @pytest.mark.asyncio
    async def test_standalone_comments_formatting(self, mock_task, mock_github_integration, mock_github_pr):
        """Standalone comments shown in separate section."""
        standalone_comment = ReviewComment(
            id=200,
            author="contributor1",
            body="Should we add a docstring here?",
            path="src/utils.py",
            line=10,
            created_at=datetime(2024, 1, 16, 9, 0, 0),
            diff_hunk=None,
            in_reply_to_id=None,
        )
        standalone_thread = CommentThread(
            original=standalone_comment,
            replies=[],
        )
        mock_github_pr.get_feedback.return_value = PRFeedback(
            reviews=[],
            standalone_threads=[standalone_thread],
        )

        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)
        result = await tool.function()

        assert "# Standalone Comments" in result
        assert "(Comments not associated with a formal review)" in result
        assert "**contributor1** at `src/utils.py` (line 10):" in result
        assert "Should we add a docstring here?" in result

    @pytest.mark.asyncio
    async def test_comment_without_line_number(self, mock_task, mock_github_integration, mock_github_pr):
        """Comment without line number formats correctly."""
        comment = ReviewComment(
            id=300,
            author="reviewer1",
            body="General comment on this file.",
            path="src/config.py",
            line=None,
            created_at=None,
            diff_hunk=None,
            in_reply_to_id=None,
        )
        thread = CommentThread(original=comment, replies=[])
        mock_github_pr.get_feedback.return_value = PRFeedback(
            reviews=[],
            standalone_threads=[thread],
        )

        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)
        result = await tool.function()

        # Should not include "(line X)" when line is None
        assert "**reviewer1** at `src/config.py`:" in result
        assert "(line" not in result

    @pytest.mark.asyncio
    async def test_multiple_reviews_and_standalone_threads(self, mock_task, mock_github_integration, mock_github_pr):
        """Both reviews and standalone threads are included when present."""
        review1 = ReviewWithComments(
            id=1,
            author="reviewer1",
            state="APPROVED",
            body="LGTM",
            submitted_at=None,
            comment_threads=[],
        )
        review2 = ReviewWithComments(
            id=2,
            author="reviewer2",
            state="COMMENTED",
            body="Minor suggestions",
            submitted_at=None,
            comment_threads=[],
        )
        standalone_comment = ReviewComment(
            id=400,
            author="observer",
            body="Interesting approach!",
            path="src/app.py",
            line=5,
            created_at=None,
            diff_hunk=None,
            in_reply_to_id=None,
        )
        standalone_thread = CommentThread(original=standalone_comment, replies=[])

        mock_github_pr.get_feedback.return_value = PRFeedback(
            reviews=[review1, review2],
            standalone_threads=[standalone_thread],
        )

        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)
        result = await tool.function()

        # Check both sections exist
        assert "# Reviews" in result
        assert "# Standalone Comments" in result

        # Check both reviews are present
        assert "## Review by reviewer1" in result
        assert "LGTM" in result
        assert "## Review by reviewer2" in result
        assert "Minor suggestions" in result

        # Check standalone comment is present
        assert "Interesting approach!" in result

    @pytest.mark.asyncio
    async def test_github_api_error(self, mock_task, mock_github_integration):
        """Returns error message when GitHub API call fails."""
        mock_github_integration.get_repository_from_url.side_effect = Exception("API rate limit exceeded")

        tool = create_get_pr_feedback_tool(mock_task, mock_github_integration)
        result = await tool.function()

        assert "Error fetching PR feedback:" in result
        assert "API rate limit exceeded" in result

    @pytest.mark.asyncio
    async def test_missing_pr_number(self, mock_github_integration):
        """Returns error message when task has no PR number."""
        task = Mock(spec=Task)
        task.github_pr_number = None
        task.codebase = Mock()
        task.codebase.repository_url = "https://github.com/test/repo"

        tool = create_get_pr_feedback_tool(task, mock_github_integration)
        result = await tool.function()

        assert "Error:" in result
        assert "PR number or repository URL" in result
