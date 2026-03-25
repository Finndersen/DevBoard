"""Tests for GitHub integration methods."""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from github import UnknownObjectException
from github.PullRequestComment import PullRequestComment
from github.PullRequestReview import PullRequestReview

from devboard.config.integration_configs import GitHubIntegrationConfig
from devboard.integrations.base import IntegrationError, ResourceNotFoundError
from devboard.integrations.github import (
    PR_CACHE_MAX_AGE,
    CommentThread,
    GitHubIntegration,
    GitHubPR,
    GitHubRepository,
    PRCacheEntry,
    PRFeedback,
    PullRequest,
    ReviewComment,
    ReviewWithComments,
)


def create_mock_review(
    review_id: int,
    author: str,
    state: str,
    body: str = "",
    submitted_at: datetime | None = None,
) -> Mock:
    """Create a mock PullRequestReview object."""
    review = Mock(spec=PullRequestReview)
    review.id = review_id
    review.user = Mock()
    review.user.login = author
    review.state = state
    review.body = body
    review.submitted_at = submitted_at or datetime(2024, 1, 1, 12, 0, 0)
    return review


def create_mock_comment(
    comment_id: int,
    author: str,
    body: str,
    path: str = "file.py",
    line: int | None = 10,
    original_line: int | None = None,
    pull_request_review_id: int | None = None,
    in_reply_to_id: int | None = None,
    created_at: datetime | None = None,
    diff_hunk: str | None = None,
) -> Mock:
    """Create a mock PullRequestComment object."""
    comment = Mock(spec=PullRequestComment)
    comment.id = comment_id
    comment.user = Mock()
    comment.user.login = author
    comment.body = body
    comment.path = path
    comment.line = line
    comment.original_line = original_line
    comment.pull_request_review_id = pull_request_review_id
    comment.in_reply_to_id = in_reply_to_id
    comment.created_at = created_at or datetime(2024, 1, 1, 12, 0, 0)
    comment.diff_hunk = diff_hunk
    return comment


def create_mock_pr(pr_number: int = 123) -> Mock:
    """Create a mock PyGithub PullRequest object."""
    pr = Mock()
    pr.number = pr_number
    pr.title = "Test PR"
    pr.state = "open"
    pr.body = "Test description"
    pr.merged = False
    pr.mergeable = True
    pr.mergeable_state = "clean"
    pr.html_url = f"https://github.com/owner/repo/pull/{pr_number}"
    pr.user = Mock()
    pr.user.login = "author"
    pr.head = Mock()
    pr.head.sha = "abc123"
    pr.get_reviews = Mock(return_value=[])
    pr.get_review_comments = Mock(return_value=[])
    return pr


@pytest.fixture
def mock_repo() -> Mock:
    """Create a mock PyGithub Repository object."""
    repo = Mock()
    repo.owner = Mock()
    repo.owner.login = "test-owner"
    repo.name = "test-repo"
    repo.full_name = "test-owner/test-repo"
    return repo


@pytest.fixture
def mock_github_repo(mock_repo: Mock) -> GitHubRepository:
    """Create a mock GitHubRepository wrapper."""
    return GitHubRepository(mock_repo)


@pytest.fixture
def mock_pr() -> Mock:
    """Create a mock PyGithub PullRequest object."""
    return create_mock_pr()


class TestGitHubPR:
    """Tests for GitHubPR wrapper class."""

    def test_pr_property(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test that pr property returns the underlying PullRequest."""
        github_pr = GitHubPR(mock_pr, mock_github_repo)
        assert github_pr.pr is mock_pr

    def test_number_property(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test that number property returns the PR number."""
        mock_pr.number = 456
        github_pr = GitHubPR(mock_pr, mock_github_repo)
        assert github_pr.number == 456

    def test_repo_property(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test that repo property returns the GitHubRepository."""
        github_pr = GitHubPR(mock_pr, mock_github_repo)
        assert github_pr.repo is mock_github_repo


class TestGitHubRepositoryPRFactory:
    """Tests for GitHubRepository.pr() factory method."""

    @pytest.mark.asyncio
    async def test_pr_factory_returns_github_pr(self, mock_repo: Mock):
        """Test that pr() factory returns a GitHubPR instance."""
        mock_pr = create_mock_pr(123)
        mock_repo.get_pull.return_value = mock_pr

        github_repo = GitHubRepository(mock_repo)
        result = await github_repo.get_pull_request(123)

        assert isinstance(result, GitHubPR)
        assert result.pr is mock_pr
        mock_repo.get_pull.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_pr_factory_raises_on_not_found(self, mock_repo: Mock):
        """Test that pr() raises ResourceNotFoundError when PR not found."""
        mock_repo.get_pull.side_effect = UnknownObjectException(404, {}, {})

        github_repo = GitHubRepository(mock_repo)
        with pytest.raises(ResourceNotFoundError) as exc_info:
            await github_repo.get_pull_request(999)

        assert "not found" in str(exc_info.value).lower()


class TestGitHubPRGetFeedback:
    """Tests for GitHubPR.get_feedback() method."""

    @pytest.mark.asyncio
    async def test_empty_feedback(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test that no reviews or comments returns empty PRFeedback."""
        mock_pr.get_reviews.return_value = []
        mock_pr.get_review_comments.return_value = []

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        assert result == PRFeedback(reviews=[], standalone_threads=[])
        assert len(result.reviews) == 0
        assert len(result.standalone_threads) == 0

    @pytest.mark.asyncio
    async def test_review_without_comments(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test review exists but has no associated comments."""
        mock_review = create_mock_review(
            review_id=100,
            author="reviewer1",
            state="APPROVED",
            body="Looks good!",
            submitted_at=datetime(2024, 1, 15, 10, 30, 0),
        )

        mock_pr.get_reviews.return_value = [mock_review]
        mock_pr.get_review_comments.return_value = []

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        assert len(result.reviews) == 1
        assert len(result.standalone_threads) == 0

        review = result.reviews[0]
        assert review == ReviewWithComments(
            id=100,
            author="reviewer1",
            state="APPROVED",
            body="Looks good!",
            submitted_at=datetime(2024, 1, 15, 10, 30, 0),
            comment_threads=[],
        )

    @pytest.mark.asyncio
    async def test_review_with_comments(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test review with associated comments linked via pull_request_review_id."""
        mock_review = create_mock_review(
            review_id=100,
            author="reviewer1",
            state="CHANGES_REQUESTED",
            body="Please fix these issues",
        )

        mock_comment1 = create_mock_comment(
            comment_id=1001,
            author="reviewer1",
            body="This needs refactoring",
            path="src/main.py",
            line=25,
            pull_request_review_id=100,
            created_at=datetime(2024, 1, 15, 10, 31, 0),
            diff_hunk="@@ -20,6 +20,10 @@ def main():",
        )

        mock_comment2 = create_mock_comment(
            comment_id=1002,
            author="reviewer1",
            body="Add error handling here",
            path="src/utils.py",
            line=42,
            pull_request_review_id=100,
            created_at=datetime(2024, 1, 15, 10, 32, 0),
        )

        mock_pr.get_reviews.return_value = [mock_review]
        mock_pr.get_review_comments.return_value = [mock_comment1, mock_comment2]

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        assert len(result.reviews) == 1
        assert len(result.standalone_threads) == 0

        review = result.reviews[0]
        assert review.id == 100
        assert review.author == "reviewer1"
        assert review.state == "CHANGES_REQUESTED"
        assert len(review.comment_threads) == 2

        thread1 = review.comment_threads[0]
        assert thread1.original == ReviewComment(
            id=1001,
            author="reviewer1",
            body="This needs refactoring",
            path="src/main.py",
            line=25,
            created_at=datetime(2024, 1, 15, 10, 31, 0),
            diff_hunk="@@ -20,6 +20,10 @@ def main():",
            in_reply_to_id=None,
        )
        assert thread1.replies == []

        thread2 = review.comment_threads[1]
        assert thread2.original.id == 1002
        assert thread2.original.body == "Add error handling here"
        assert thread2.replies == []

    @pytest.mark.asyncio
    async def test_comment_thread_with_replies(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test comments threaded via in_reply_to_id are grouped correctly."""
        mock_review = create_mock_review(
            review_id=100,
            author="reviewer1",
            state="COMMENTED",
            body="",
        )

        original_comment = create_mock_comment(
            comment_id=1001,
            author="reviewer1",
            body="This function is too complex",
            path="src/complex.py",
            line=50,
            pull_request_review_id=100,
            created_at=datetime(2024, 1, 15, 10, 0, 0),
        )

        reply1 = create_mock_comment(
            comment_id=1002,
            author="developer",
            body="I'll refactor this",
            path="src/complex.py",
            line=50,
            pull_request_review_id=100,
            in_reply_to_id=1001,
            created_at=datetime(2024, 1, 15, 11, 0, 0),
        )

        reply2 = create_mock_comment(
            comment_id=1003,
            author="reviewer1",
            body="Thanks!",
            path="src/complex.py",
            line=50,
            pull_request_review_id=100,
            in_reply_to_id=1001,
            created_at=datetime(2024, 1, 15, 12, 0, 0),
        )

        mock_pr.get_reviews.return_value = [mock_review]
        mock_pr.get_review_comments.return_value = [original_comment, reply1, reply2]

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        assert len(result.reviews) == 1
        review = result.reviews[0]
        assert len(review.comment_threads) == 1

        thread = review.comment_threads[0]
        assert thread.original.id == 1001
        assert thread.original.body == "This function is too complex"
        assert len(thread.replies) == 2

        assert thread.replies[0].id == 1002
        assert thread.replies[0].author == "developer"
        assert thread.replies[0].body == "I'll refactor this"
        assert thread.replies[0].in_reply_to_id == 1001

        assert thread.replies[1].id == 1003
        assert thread.replies[1].author == "reviewer1"
        assert thread.replies[1].body == "Thanks!"

    @pytest.mark.asyncio
    async def test_standalone_comments(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test comments not associated with any review are returned as standalone threads."""
        standalone_comment = create_mock_comment(
            comment_id=2001,
            author="collaborator",
            body="Quick question about this line",
            path="src/api.py",
            line=100,
            pull_request_review_id=None,
            created_at=datetime(2024, 1, 20, 9, 0, 0),
        )

        mock_pr.get_reviews.return_value = []
        mock_pr.get_review_comments.return_value = [standalone_comment]

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        assert len(result.reviews) == 0
        assert len(result.standalone_threads) == 1

        thread = result.standalone_threads[0]
        assert thread == CommentThread(
            original=ReviewComment(
                id=2001,
                author="collaborator",
                body="Quick question about this line",
                path="src/api.py",
                line=100,
                created_at=datetime(2024, 1, 20, 9, 0, 0),
                diff_hunk=None,
                in_reply_to_id=None,
            ),
            replies=[],
        )

    @pytest.mark.asyncio
    async def test_multiple_reviews_multiple_threads(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test multiple reviews each with multiple comment threads."""
        review1 = create_mock_review(
            review_id=100,
            author="reviewer1",
            state="CHANGES_REQUESTED",
            body="Several issues to address",
            submitted_at=datetime(2024, 1, 10, 10, 0, 0),
        )

        review2 = create_mock_review(
            review_id=200,
            author="reviewer2",
            state="APPROVED",
            body="LGTM after fixes",
            submitted_at=datetime(2024, 1, 12, 14, 0, 0),
        )

        # Comments for review 1
        r1_comment1 = create_mock_comment(
            comment_id=1001,
            author="reviewer1",
            body="Fix naming convention",
            path="src/models.py",
            line=10,
            pull_request_review_id=100,
            created_at=datetime(2024, 1, 10, 10, 1, 0),
        )

        r1_comment1_reply = create_mock_comment(
            comment_id=1002,
            author="developer",
            body="Fixed!",
            path="src/models.py",
            line=10,
            pull_request_review_id=100,
            in_reply_to_id=1001,
            created_at=datetime(2024, 1, 10, 11, 0, 0),
        )

        r1_comment2 = create_mock_comment(
            comment_id=1003,
            author="reviewer1",
            body="Add type hints",
            path="src/utils.py",
            line=5,
            pull_request_review_id=100,
            created_at=datetime(2024, 1, 10, 10, 2, 0),
        )

        # Comments for review 2
        r2_comment1 = create_mock_comment(
            comment_id=2001,
            author="reviewer2",
            body="Nice improvement!",
            path="src/api.py",
            line=30,
            pull_request_review_id=200,
            created_at=datetime(2024, 1, 12, 14, 1, 0),
        )

        # Standalone comment
        standalone = create_mock_comment(
            comment_id=3001,
            author="observer",
            body="Just passing by",
            path="README.md",
            line=1,
            pull_request_review_id=None,
            created_at=datetime(2024, 1, 11, 8, 0, 0),
        )

        mock_pr.get_reviews.return_value = [review1, review2]
        mock_pr.get_review_comments.return_value = [
            r1_comment1,
            r1_comment1_reply,
            r1_comment2,
            r2_comment1,
            standalone,
        ]

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        # Check reviews
        assert len(result.reviews) == 2

        # First review
        rev1 = result.reviews[0]
        assert rev1.id == 100
        assert rev1.author == "reviewer1"
        assert rev1.state == "CHANGES_REQUESTED"
        assert len(rev1.comment_threads) == 2

        rev1_thread1 = rev1.comment_threads[0]
        assert rev1_thread1.original.id == 1001
        assert len(rev1_thread1.replies) == 1
        assert rev1_thread1.replies[0].id == 1002

        rev1_thread2 = rev1.comment_threads[1]
        assert rev1_thread2.original.id == 1003
        assert len(rev1_thread2.replies) == 0

        # Second review
        rev2 = result.reviews[1]
        assert rev2.id == 200
        assert rev2.author == "reviewer2"
        assert rev2.state == "APPROVED"
        assert len(rev2.comment_threads) == 1
        assert rev2.comment_threads[0].original.id == 2001

        # Standalone threads
        assert len(result.standalone_threads) == 1
        assert result.standalone_threads[0].original.id == 3001
        assert result.standalone_threads[0].original.author == "observer"

    @pytest.mark.asyncio
    async def test_nested_replies(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test that nested replies (replies to replies) are flattened into a single list."""
        mock_review = create_mock_review(
            review_id=100,
            author="reviewer",
            state="COMMENTED",
            body="",
        )

        original = create_mock_comment(
            comment_id=1,
            author="reviewer",
            body="Original comment",
            pull_request_review_id=100,
            created_at=datetime(2024, 1, 1, 10, 0, 0),
        )

        reply_to_original = create_mock_comment(
            comment_id=2,
            author="dev",
            body="Reply to original",
            pull_request_review_id=100,
            in_reply_to_id=1,
            created_at=datetime(2024, 1, 1, 11, 0, 0),
        )

        reply_to_reply = create_mock_comment(
            comment_id=3,
            author="reviewer",
            body="Reply to reply",
            pull_request_review_id=100,
            in_reply_to_id=2,
            created_at=datetime(2024, 1, 1, 12, 0, 0),
        )

        mock_pr.get_reviews.return_value = [mock_review]
        mock_pr.get_review_comments.return_value = [original, reply_to_original, reply_to_reply]

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        assert len(result.reviews) == 1
        assert len(result.reviews[0].comment_threads) == 1

        thread = result.reviews[0].comment_threads[0]
        assert thread.original.id == 1
        assert len(thread.replies) == 2
        assert thread.replies[0].id == 2
        assert thread.replies[1].id == 3

    @pytest.mark.asyncio
    async def test_comment_with_null_user(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test handling of comments with null user."""
        mock_review = create_mock_review(
            review_id=100,
            author="reviewer",
            state="COMMENTED",
            body="",
        )
        mock_review.user = None

        mock_comment = create_mock_comment(
            comment_id=1001,
            author="author",
            body="Some comment",
            pull_request_review_id=100,
        )
        mock_comment.user = None

        mock_pr.get_reviews.return_value = [mock_review]
        mock_pr.get_review_comments.return_value = [mock_comment]

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        assert len(result.reviews) == 1
        assert result.reviews[0].author == "Unknown"
        assert len(result.reviews[0].comment_threads) == 1
        assert result.reviews[0].comment_threads[0].original.author == "Unknown"

    @pytest.mark.asyncio
    async def test_comment_uses_original_line_when_line_is_none(
        self, mock_pr: Mock, mock_github_repo: GitHubRepository
    ):
        """Test that original_line is used as fallback when line is None."""
        standalone_comment = create_mock_comment(
            comment_id=1001,
            author="reviewer",
            body="Comment on original line",
            path="src/file.py",
            line=None,
            original_line=42,
            pull_request_review_id=None,
        )

        mock_pr.get_reviews.return_value = []
        mock_pr.get_review_comments.return_value = [standalone_comment]

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        assert len(result.standalone_threads) == 1
        assert result.standalone_threads[0].original.line == 42

    @pytest.mark.asyncio
    async def test_replies_sorted_by_created_at(self, mock_pr: Mock, mock_github_repo: GitHubRepository):
        """Test that replies within a thread are sorted by created_at."""
        mock_review = create_mock_review(
            review_id=100,
            author="reviewer",
            state="COMMENTED",
            body="",
        )

        original = create_mock_comment(
            comment_id=1,
            author="reviewer",
            body="Original",
            pull_request_review_id=100,
            created_at=datetime(2024, 1, 1, 10, 0, 0),
        )

        # Create replies in non-chronological order
        reply_late = create_mock_comment(
            comment_id=3,
            author="dev2",
            body="Late reply",
            pull_request_review_id=100,
            in_reply_to_id=1,
            created_at=datetime(2024, 1, 1, 14, 0, 0),
        )

        reply_early = create_mock_comment(
            comment_id=2,
            author="dev1",
            body="Early reply",
            pull_request_review_id=100,
            in_reply_to_id=1,
            created_at=datetime(2024, 1, 1, 11, 0, 0),
        )

        reply_middle = create_mock_comment(
            comment_id=4,
            author="dev3",
            body="Middle reply",
            pull_request_review_id=100,
            in_reply_to_id=1,
            created_at=datetime(2024, 1, 1, 12, 0, 0),
        )

        mock_pr.get_reviews.return_value = [mock_review]
        mock_pr.get_review_comments.return_value = [original, reply_late, reply_early, reply_middle]

        github_pr = GitHubPR(mock_pr, mock_github_repo)
        result = await github_pr.get_feedback()

        thread = result.reviews[0].comment_threads[0]
        assert len(thread.replies) == 3
        assert thread.replies[0].id == 2  # Early reply
        assert thread.replies[1].id == 4  # Middle reply
        assert thread.replies[2].id == 3  # Late reply


class TestGetUserPullRequests:
    """Tests for GitHubIntegration.get_user_open_pull_requests()."""

    @pytest.fixture
    def github_integration(self) -> GitHubIntegration:
        config = GitHubIntegrationConfig(api_token="ghp_test_token", base_url="https://api.github.com")
        with patch("devboard.integrations.github.Github"):
            return GitHubIntegration(config)

    @pytest.mark.asyncio
    async def test_returns_open_prs(self, github_integration: GitHubIntegration):
        graphql_response = {
            "data": {
                "search": {
                    "nodes": [
                        {
                            "number": 42,
                            "title": "Fix the thing",
                            "url": "https://github.com/owner/repo/pull/42",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "updatedAt": "2026-03-01T12:00:00Z",
                            "repository": {"nameWithOwner": "owner/repo"},
                            "reviewDecision": "APPROVED",
                            "totalCommentsCount": 5,
                            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]},
                        },
                        {
                            "number": 7,
                            "title": "Add feature",
                            "url": "https://github.com/owner/other/pull/7",
                            "mergeable": "CONFLICTING",
                            "mergeStateStatus": "DIRTY",
                            "updatedAt": "2026-03-01T12:00:00Z",
                            "repository": {"nameWithOwner": "owner/other"},
                            "reviewDecision": "CHANGES_REQUESTED",
                            "totalCommentsCount": 2,
                            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "FAILURE"}}}]},
                        },
                    ]
                }
            }
        }

        mock_response = Mock()
        mock_response.json.return_value = graphql_response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await github_integration.get_user_open_pull_requests()

        assert result == [
            PullRequest(
                number=42,
                title="Fix the thing",
                html_url="https://github.com/owner/repo/pull/42",
                mergeable_state="CLEAN",
                repo_full_name="owner/repo",
                updated_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
                review_decision="APPROVED",
                ci_status="SUCCESS",
                comment_count=5,
            ),
            PullRequest(
                number=7,
                title="Add feature",
                html_url="https://github.com/owner/other/pull/7",
                mergeable_state="DIRTY",
                repo_full_name="owner/other",
                updated_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
                review_decision="CHANGES_REQUESTED",
                ci_status="FAILURE",
                comment_count=2,
            ),
        ]

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "https://api.github.com/graphql"
        assert call_kwargs[1]["headers"]["Authorization"] == "Bearer ghp_test_token"
        # Verify staleness filter is included in the search query variable
        variables = call_kwargs[1]["json"]["variables"]
        assert "updated:>=" in variables["q"]

    @pytest.mark.asyncio
    async def test_skips_null_nodes(self, github_integration: GitHubIntegration):
        graphql_response = {
            "data": {
                "search": {
                    "nodes": [
                        None,
                        {
                            "number": 1,
                            "title": "Valid PR",
                            "url": "https://github.com/owner/repo/pull/1",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "updatedAt": "2026-03-01T12:00:00Z",
                            "repository": {"nameWithOwner": "owner/repo"},
                            "reviewDecision": None,
                            "totalCommentsCount": 0,
                            "commits": {"nodes": []},
                        },
                        None,
                    ]
                }
            }
        }

        mock_response = Mock()
        mock_response.json.return_value = graphql_response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await github_integration.get_user_open_pull_requests()

        assert len(result) == 1
        assert result[0].number == 1

    @pytest.mark.asyncio
    async def test_graphql_errors_raise_integration_error(self, github_integration: GitHubIntegration):
        graphql_response = {"errors": [{"message": "Something went wrong"}]}

        mock_response = Mock()
        mock_response.json.return_value = graphql_response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(IntegrationError, match="GraphQL error"):
                await github_integration.get_user_open_pull_requests()

    @pytest.mark.asyncio
    async def test_ghe_graphql_url(self):
        config = GitHubIntegrationConfig(api_token="ghp_test", base_url="https://github.example.com/api/v3")
        with patch("devboard.integrations.github.Github"):
            integration = GitHubIntegration(config)

        graphql_response = {"data": {"search": {"nodes": []}}}
        mock_response = Mock()
        mock_response.json.return_value = graphql_response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await integration.get_user_open_pull_requests()

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[0][0] == "https://github.example.com/api/graphql"


def _make_graphql_response_for_single_pr(
    number: int = 42,
    repo: str = "owner/repo",
    title: str = "Test PR",
) -> dict:
    """Build a minimal GraphQL response for get_pull_request_status."""
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "number": number,
                    "title": title,
                    "url": f"https://github.com/{repo}/pull/{number}",
                    "updatedAt": "2026-03-01T12:00:00Z",
                    "state": "OPEN",
                    "mergeStateStatus": "CLEAN",
                    "mergeQueueEntry": None,
                    "reviewDecision": None,
                    "totalCommentsCount": 0,
                    "commits": {"nodes": []},
                    "repository": {"nameWithOwner": repo},
                }
            }
        }
    }


def _make_graphql_response_for_batch(prs: list[dict]) -> dict:
    """Build a minimal GraphQL response for get_user_open_pull_requests."""
    return {"data": {"search": {"nodes": prs}}}


def _make_batch_pr_node(number: int = 42, repo: str = "owner/repo", title: str = "Test PR") -> dict:
    return {
        "number": number,
        "title": title,
        "url": f"https://github.com/{repo}/pull/{number}",
        "updatedAt": "2026-03-01T12:00:00Z",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "mergeQueueEntry": None,
        "reviewDecision": None,
        "totalCommentsCount": 0,
        "commits": {"nodes": []},
        "repository": {"nameWithOwner": repo},
    }


@pytest.fixture(autouse=True)
def clear_pr_cache():
    """Clear class-level PR cache before and after each test to prevent pollution."""
    GitHubIntegration._pr_cache.clear()
    GitHubIntegration._last_batch_fetch_at = 0.0
    yield
    GitHubIntegration._pr_cache.clear()
    GitHubIntegration._last_batch_fetch_at = 0.0


class TestGetPullRequestStatusCache:
    """Tests for caching behaviour in get_pull_request_status."""

    @pytest.fixture
    def github_integration(self) -> GitHubIntegration:
        config = GitHubIntegrationConfig(api_token="ghp_test_token", base_url="https://api.github.com")
        with patch("devboard.integrations.github.Github"):
            return GitHubIntegration(config)

    def _mock_client_context(self, mock_client: AsyncMock) -> tuple:
        """Helper to configure AsyncClient mock."""
        return mock_client

    @pytest.mark.asyncio
    async def test_cache_hit_skips_github_api(self, github_integration: GitHubIntegration):
        """Second call within cache window should not call GitHub API."""
        response = _make_graphql_response_for_single_pr()
        mock_response = Mock()
        mock_response.json.return_value = response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result1 = await github_integration.get_pull_request_status("owner", "repo", 42)
            result2 = await github_integration.get_pull_request_status("owner", "repo", 42)

        assert result1 == result2
        assert mock_client.post.call_count == 1  # Only fetched once

    @pytest.mark.asyncio
    async def test_cache_miss_after_expiry_refetches(self, github_integration: GitHubIntegration):
        """After cache entry expires, a fresh fetch should occur."""
        response = _make_graphql_response_for_single_pr()
        mock_response = Mock()
        mock_response.json.return_value = response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await github_integration.get_pull_request_status("owner", "repo", 42)

            # Manually expire the cache entry
            key = GitHubIntegration._cache_key("owner/repo", 42)
            GitHubIntegration._pr_cache[key] = PRCacheEntry(
                data=GitHubIntegration._pr_cache[key].data,
                fetched_at=time.time() - PR_CACHE_MAX_AGE - 1,
            )

            await github_integration.get_pull_request_status("owner", "repo", 42)

        assert mock_client.post.call_count == 2  # Fetched twice

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, github_integration: GitHubIntegration):
        """force_refresh=True should always fetch from GitHub regardless of cache."""
        response = _make_graphql_response_for_single_pr()
        mock_response = Mock()
        mock_response.json.return_value = response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await github_integration.get_pull_request_status("owner", "repo", 42)
            await github_integration.get_pull_request_status("owner", "repo", 42, force_refresh=True)

        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_fetch_warms_single_pr_cache(self, github_integration: GitHubIntegration):
        """get_user_open_pull_requests should populate cache used by get_pull_request_status."""
        batch_response = _make_graphql_response_for_batch([_make_batch_pr_node(42, "owner/repo")])
        mock_response = Mock()
        mock_response.json.return_value = batch_response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            # Warm cache via batch fetch
            await github_integration.get_user_open_pull_requests()

            # Single PR fetch should hit the cache populated by batch
            await github_integration.get_pull_request_status("owner", "repo", 42)

        assert mock_client.post.call_count == 1  # Only the batch call, single PR hit cache


class TestGetUserPullRequestsCache:
    """Tests for caching behaviour in get_user_open_pull_requests."""

    @pytest.fixture
    def github_integration(self) -> GitHubIntegration:
        config = GitHubIntegrationConfig(api_token="ghp_test_token", base_url="https://api.github.com")
        with patch("devboard.integrations.github.Github"):
            return GitHubIntegration(config)

    @pytest.mark.asyncio
    async def test_batch_cache_hit_skips_github_api(self, github_integration: GitHubIntegration):
        """Second batch call within cache window should return cached result."""
        batch_response = _make_graphql_response_for_batch([_make_batch_pr_node(1), _make_batch_pr_node(2)])
        mock_response = Mock()
        mock_response.json.return_value = batch_response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result1 = await github_integration.get_user_open_pull_requests()
            result2 = await github_integration.get_user_open_pull_requests()

        assert result1 == result2
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_batch_cache_miss_after_expiry(self, github_integration: GitHubIntegration):
        """After batch cache expires, a fresh fetch should occur."""
        batch_response = _make_graphql_response_for_batch([_make_batch_pr_node(1)])
        mock_response = Mock()
        mock_response.json.return_value = batch_response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await github_integration.get_user_open_pull_requests()

            # Expire batch cache
            GitHubIntegration._last_batch_fetch_at = time.time() - PR_CACHE_MAX_AGE - 1

            await github_integration.get_user_open_pull_requests()

        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_batch_cache(self, github_integration: GitHubIntegration):
        """force_refresh=True should bypass the batch cache."""
        batch_response = _make_graphql_response_for_batch([_make_batch_pr_node(1)])
        mock_response = Mock()
        mock_response.json.return_value = batch_response
        mock_response.raise_for_status = Mock()

        with patch("devboard.integrations.github.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await github_integration.get_user_open_pull_requests()
            await github_integration.get_user_open_pull_requests(force_refresh=True)

        assert mock_client.post.call_count == 2
