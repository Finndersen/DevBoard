"""GitHub integration for accessing PRs, commits, issues, and branches."""

import logging
from typing import Any

from github import (
    BadCredentialsException,
    Github,
    GithubException,
    RateLimitExceededException,
    UnknownObjectException,
)
from github.Auth import Token

from devboard.config.integration_configs import GitHubIntegrationConfig
from devboard.services.config_service import ConfigService

from .base import (
    AuthenticationError,
    BaseIntegration,
    IntegrationConfigurationError,
    IntegrationError,
    RateLimitError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


class GitHubIntegration(BaseIntegration):
    """Integration for GitHub API access."""

    integration_type = "github"

    def __init__(self, config: GitHubIntegrationConfig):
        """Initialize with GitHub configuration and client."""
        self.config = config
        try:
            self.client = Github(auth=Token(config.api_token), base_url=config.base_url)
            logger.info("Initialized GitHub integration")
        except Exception as e:
            logger.error(f"Failed to initialize GitHub integration: {e}")
            raise AuthenticationError(f"Failed to initialize GitHub: {e}") from e

    @classmethod
    def create(cls, config_service: ConfigService) -> "GitHubIntegration":
        """Create GitHub integration instance with configuration from database and environment."""
        try:
            # Get configuration from config service (includes database + environment)
            config = config_service.get_config(GitHubIntegrationConfig)
            if not config:
                raise IntegrationConfigurationError(
                    "GitHub configuration not found or invalid. Please configure the GitHub integration."
                )
            return cls(config)
        except Exception as e:
            logger.error(f"Failed to create GitHub integration: {e}")
            raise IntegrationConfigurationError(f"GitHub configuration error: {e}") from e

    async def test_connection(self) -> bool:
        """Test GitHub API connection."""
        try:
            # Test connection by getting current user info
            self.client.get_user()
            return True
        except Exception as e:
            logger.error(f"GitHub connection test failed: {e}")
            return False

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
        """Get details of a specific pull request."""
        try:
            repo_obj = self.client.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(pr_number)
            return pr.raw_data  # type: ignore[return-value]
        except UnknownObjectException as e:
            raise ResourceNotFoundError(f"Pull request #{pr_number} not found in {owner}/{repo}") from e
        except BadCredentialsException as e:
            raise AuthenticationError(f"GitHub authentication failed: {e}") from e
        except RateLimitExceededException as e:
            raise RateLimitError(f"GitHub rate limit exceeded: {e}") from e
        except GithubException as e:
            logger.error(f"GitHub error in get_pull_request({owner}/{repo}#{pr_number}): {e}")
            raise IntegrationError(f"GitHub error: {e}") from e

    async def get_pull_request_comments(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Get comments for a pull request."""
        try:
            repo_obj = self.client.get_repo(f"{owner}/{repo}")
            pr = repo_obj.get_pull(pr_number)
            comments = pr.get_review_comments()
            return [comment.raw_data for comment in comments]  # type: ignore[return-value]
        except BadCredentialsException as e:
            raise AuthenticationError(f"GitHub authentication failed: {e}") from e
        except RateLimitExceededException as e:
            raise RateLimitError(f"GitHub rate limit exceeded: {e}") from e
        except GithubException as e:
            logger.error(f"GitHub error in get_pull_request_comments({owner}/{repo}#{pr_number}): {e}")
            raise IntegrationError(f"GitHub error: {e}") from e

    async def get_commit(self, owner: str, repo: str, sha: str) -> dict[str, Any]:
        """Get details of a specific commit."""
        try:
            repo_obj = self.client.get_repo(f"{owner}/{repo}")
            commit = repo_obj.get_commit(sha)
            return commit.raw_data  # type: ignore[return-value]
        except BadCredentialsException as e:
            raise AuthenticationError(f"GitHub authentication failed: {e}") from e
        except RateLimitExceededException as e:
            raise RateLimitError(f"GitHub rate limit exceeded: {e}") from e
        except GithubException as e:
            logger.error(f"GitHub error in get_commit({owner}/{repo}/{sha}): {e}")
            raise IntegrationError(f"GitHub error: {e}") from e

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
        """Get details of a specific issue."""
        try:
            repo_obj = self.client.get_repo(f"{owner}/{repo}")
            issue = repo_obj.get_issue(issue_number)
            return issue.raw_data  # type: ignore[return-value]
        except BadCredentialsException as e:
            raise AuthenticationError(f"GitHub authentication failed: {e}") from e
        except RateLimitExceededException as e:
            raise RateLimitError(f"GitHub rate limit exceeded: {e}") from e
        except GithubException as e:
            logger.error(f"GitHub error in get_issue({owner}/{repo}#{issue_number}): {e}")
            raise IntegrationError(f"GitHub error: {e}") from e

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository information."""
        try:
            repo_obj = self.client.get_repo(f"{owner}/{repo}")
            return repo_obj.raw_data  # type: ignore[return-value]
        except BadCredentialsException as e:
            raise AuthenticationError(f"GitHub authentication failed: {e}") from e
        except RateLimitExceededException as e:
            raise RateLimitError(f"GitHub rate limit exceeded: {e}") from e
        except GithubException as e:
            logger.error(f"GitHub error in get_repository({owner}/{repo}): {e}")
            raise IntegrationError(f"GitHub error: {e}") from e

    async def list_branches(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """List branches in a repository."""
        try:
            repo_obj = self.client.get_repo(f"{owner}/{repo}")
            branches = repo_obj.get_branches()
            return [branch.raw_data for branch in branches]  # type: ignore[return-value]
        except BadCredentialsException as e:
            raise AuthenticationError(f"GitHub authentication failed: {e}") from e
        except RateLimitExceededException as e:
            raise RateLimitError(f"GitHub rate limit exceeded: {e}") from e
        except GithubException as e:
            logger.error(f"GitHub error in list_branches({owner}/{repo}): {e}")
            raise IntegrationError(f"GitHub error: {e}") from e

    async def search_issues(self, query: str, owner: str | None = None, repo: str | None = None) -> dict[str, Any]:
        """Search issues across GitHub."""
        try:
            # Build search query
            search_query = query
            if owner and repo:
                search_query += f" repo:{owner}/{repo}"

            issues = self.client.search_issues(search_query)

            # Convert to dict format similar to REST API response
            return {
                "items": [issue.raw_data for issue in issues],
                "total_count": issues.totalCount,
            }  # type: ignore[return-value]
        except BadCredentialsException as e:
            raise AuthenticationError(f"GitHub authentication failed: {e}") from e
        except RateLimitExceededException as e:
            raise RateLimitError(f"GitHub rate limit exceeded: {e}") from e
        except GithubException as e:
            logger.error(f"GitHub error in search_issues({query}): {e}")
            raise IntegrationError(f"GitHub error: {e}") from e

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict[str, Any]:
        """Create a new pull request."""
        try:
            repo_obj = self.client.get_repo(f"{owner}/{repo}")
            pr = repo_obj.create_pull(title=title, body=body, head=head, base=base)
            return pr.raw_data  # type: ignore[return-value]
        except BadCredentialsException as e:
            raise AuthenticationError(f"GitHub authentication failed: {e}") from e
        except RateLimitExceededException as e:
            raise RateLimitError(f"GitHub rate limit exceeded: {e}") from e
        except GithubException as e:
            logger.error(f"GitHub error in create_pull_request({owner}/{repo}): {e}")
            raise IntegrationError(f"GitHub error: {e}") from e
