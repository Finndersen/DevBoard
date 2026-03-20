"""GitHub context provider for PR, issue, and repository context."""

import re
from typing import Any
from urllib.parse import urlparse

import logfire
from github.Commit import Commit
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository

from devboard.config.integration_configs import GitHubIntegrationConfig

# Get database session and create config service
from devboard.db.database import get_db
from devboard.db.repositories import ConfigurationRepository
from devboard.integrations.github import GitHubIntegration
from devboard.services.config_service import ConfigService

from .base import (
    BaseContextProvider,
    ContextProviderUnavailable,
    ContextRetrievalError,
    ContextStrategy,
    DescriptionGenerationError,
    ResourceHandlingError,
)


class GitHubContextProvider(BaseContextProvider):
    """Context provider for GitHub resources (PRs, issues, commits, repositories)."""

    provider_type = "github"

    @classmethod
    def create_instance(cls) -> "GitHubContextProvider":
        """Create an instance of the GitHub context provider.

        Gets GitHub configuration and creates integration instance.

        Returns:
            Configured GitHubContextProvider instance

        Raises:
            ContextProviderUnavailable: If GitHub configuration is missing or invalid
        """
        try:
            session = next(get_db())
            config_repo = ConfigurationRepository(session)
            config_service = ConfigService(config_repo)

            # Get GitHub configuration
            config = config_service.get_config(GitHubIntegrationConfig)
            if not config:
                raise ContextProviderUnavailable(
                    "GitHub configuration not found or invalid. Please configure the GitHub integration."
                )

            integration = GitHubIntegration(config)
            return cls(integration)
        except Exception as e:
            raise ContextProviderUnavailable(f"Failed to initialize GitHub integration: {e}") from e

    def __init__(self, integration: GitHubIntegration):
        """Initialize with GitHub integration."""
        self.integration = integration

    @classmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        """Check if URI is a GitHub resource."""
        parsed = urlparse(resource_uri)
        return parsed.netloc in ["github.com", "www.github.com"]

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        """Determine strategy based on resource scope.

        Small-scope resources (single issues, PRs, commits) are EAGER.
        Large-scope resources (entire repos, searches) are ON_DEMAND.
        """
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        parsed = self._parse_github_url(resource_uri)
        if not parsed:
            return ContextStrategy.ON_DEMAND

        resource_type = parsed.get("type")

        # Small-scope resources that can be loaded eagerly
        if resource_type in ("pull", "issues", "commit"):
            return ContextStrategy.EAGER
        # Large-scope resources requiring focused querying
        else:
            return ContextStrategy.ON_DEMAND

    def _parse_github_url(self, url: str) -> dict[str, str] | None:
        """Parse GitHub URL to extract components."""
        # Handle URLs like:
        # https://github.com/owner/repo/pull/123
        # https://github.com/owner/repo/issues/456
        # https://github.com/owner/repo/commit/abc123
        # https://github.com/owner/repo

        pattern = r"github\.com/([^/]+)/([^/]+)(?:/([^/]+)(?:/(\d+|[a-f0-9]+))?)?"
        match = re.search(pattern, url)

        if not match:
            return None

        owner, repo, resource_type, identifier = match.groups()

        result = {"owner": owner, "repo": repo}
        if resource_type:
            result["type"] = resource_type
        if identifier:
            result["id"] = identifier

        return result

    def _pr_to_dict(self, pr: PullRequest) -> dict[str, Any]:
        """Serialize PyGithub PullRequest to dict."""
        return {
            "title": pr.title,
            "state": pr.state,
            "body": pr.body or "",
            "user": {"login": pr.user.login if pr.user else "Unknown"},
            "html_url": pr.html_url,
            "number": pr.number,
            "merged": pr.merged,
            "mergeable": pr.mergeable,
        }

    def _issue_to_dict(self, issue: Issue) -> dict[str, Any]:
        """Serialize PyGithub Issue to dict."""
        return {
            "title": issue.title,
            "state": issue.state,
            "body": issue.body or "",
            "user": {"login": issue.user.login if issue.user else "Unknown"},
            "html_url": issue.html_url,
            "number": issue.number,
        }

    def _commit_to_dict(self, commit: Commit) -> dict[str, Any]:
        """Serialize PyGithub Commit to dict."""
        return {
            "sha": commit.sha,
            "html_url": commit.html_url,
            "commit": {
                "message": commit.commit.message if commit.commit else "",
                "author": {
                    "name": commit.commit.author.name if commit.commit and commit.commit.author else "Unknown",
                },
            },
        }

    def _repo_to_dict(self, repo: Repository) -> dict[str, Any]:
        """Serialize PyGithub Repository to dict."""
        return {
            "full_name": repo.full_name,
            "description": repo.description or "",
            "language": repo.language or "Unknown",
            "html_url": repo.html_url,
        }

    async def get_resource(self, resource_uri: str) -> dict[str, Any]:
        """Get full resource data for EAGER strategy (small-scope resources)."""
        with logfire.span("github_context_provider.get_resource", resource_uri=resource_uri):
            if not self.can_handle_uri(resource_uri):
                raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

            try:
                parsed = self._parse_github_url(resource_uri)
                if not parsed:
                    raise ResourceHandlingError(f"Invalid GitHub URL format: {resource_uri}")

                owner, repo = parsed["owner"], parsed["repo"]
                resource_type = parsed.get("type")
                resource_id = parsed.get("id")

                logfire.info(
                    "Retrieving GitHub resource",
                    owner=owner,
                    repo=repo,
                    resource_type=resource_type,
                    resource_id=resource_id,
                )

                github_repo = await self.integration.get_repository(owner, repo)

                # Load full data for small-scope resources
                if resource_type == "pull":
                    assert resource_id is not None, "Missing PR number in URL"
                    github_pr = await github_repo.get_pull_request(int(resource_id))
                    return {"type": "pull_request", "data": self._pr_to_dict(github_pr.pr), "uri": resource_uri}
                elif resource_type == "issues":
                    assert resource_id is not None, "Missing issue number in URL"
                    issue = await github_repo.get_issue(int(resource_id))
                    return {"type": "issue", "data": self._issue_to_dict(issue), "uri": resource_uri}
                elif resource_type == "commit":
                    assert resource_id is not None, "Missing commit SHA in URL"
                    commit = await github_repo.get_commit(resource_id)
                    return {"type": "commit", "data": self._commit_to_dict(commit), "uri": resource_uri}
                else:
                    raise ContextRetrievalError(f"Unsupported resource type for EAGER loading: {resource_type}")

            except Exception as e:
                if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                    logfire.warn(
                        "GitHub resource retrieval failed",
                        error_type=type(e).__name__,
                        error=str(e),
                    )
                    raise
                logfire.exception("Unexpected error retrieving GitHub resource")
                raise ContextRetrievalError(f"Failed to get GitHub resource: {e}") from e

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        """Get query-relevant context from GitHub resource."""
        with logfire.span(
            "github_context_provider.get_relevant_context",
            resource_uri=resource_uri,
            query_length=len(query),
        ):
            if not self.can_handle_uri(resource_uri):
                raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

            try:
                parsed = self._parse_github_url(resource_uri)
                if not parsed:
                    raise ResourceHandlingError(f"Invalid GitHub URL format: {resource_uri}")

                owner, repo = parsed["owner"], parsed["repo"]
                resource_type = parsed.get("type")
                resource_id = parsed.get("id")

                logfire.info(
                    "Processing GitHub context request",
                    owner=owner,
                    repo=repo,
                    resource_type=resource_type,
                    resource_id=resource_id,
                )

                github_repo = await self.integration.get_repository(owner, repo)

                # Fetch appropriate data based on resource type
                if resource_type == "pull":
                    if not resource_id:
                        raise ResourceHandlingError("Missing PR number in URL")
                    github_pr = await github_repo.get_pull_request(int(resource_id))
                    pr = github_pr.pr

                    # Create focused summary based on query
                    context = f"""
GitHub Pull Request: {pr.title}
URL: {resource_uri}
Status: {pr.state}
Author: {pr.user.login if pr.user else "Unknown"}
Description: {pr.body or "No description"}

Query: {query}

Based on this PR data and comments, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                    logfire.info("GitHub context generated", context_length=len(context))
                    return context

                elif resource_type == "issues":
                    if not resource_id:
                        raise ResourceHandlingError("Missing issue number in URL")
                    issue = await github_repo.get_issue(int(resource_id))

                    context = f"""
GitHub Issue: {issue.title}
URL: {resource_uri}
Status: {issue.state}
Author: {issue.user.login if issue.user else "Unknown"}
Description: {issue.body or "No description"}

Query: {query}

Based on this issue data, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                    logfire.info("GitHub context generated", context_length=len(context))
                    return context

                elif resource_type == "commit":
                    if not resource_id:
                        raise ResourceHandlingError("Missing commit SHA in URL")
                    commit = await github_repo.get_commit(resource_id)

                    context = f"""
GitHub Commit: {commit.commit.message if commit.commit else "No message"}
URL: {resource_uri}
Author: {commit.commit.author.name if commit.commit and commit.commit.author else "Unknown"}
SHA: {resource_id}

Query: {query}

Based on this commit data, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                    logfire.info("GitHub context generated", context_length=len(context))
                    return context

                else:
                    # Repository-level resource
                    context = f"""
GitHub Repository: {github_repo.full_name}
URL: {resource_uri}
Description: {github_repo.description or "No description"}
Language: {github_repo.language or "Unknown"}

Query: {query}

Based on this repository data, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                    logfire.info("GitHub context generated", context_length=len(context))
                    return context

            except Exception as e:
                if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                    logfire.warn("GitHub context retrieval failed", error_type=type(e).__name__, error=str(e))
                    raise
                logfire.exception("Unexpected error in GitHub context retrieval")
                raise ContextRetrievalError(f"Failed to get GitHub context: {e}") from e

    async def generate_resource_description(self, resource_uri: str) -> str:
        """Generate description for GitHub resource."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            parsed = self._parse_github_url(resource_uri)
            if not parsed:
                raise ResourceHandlingError(f"Invalid GitHub URL format: {resource_uri}")

            owner, repo = parsed["owner"], parsed["repo"]
            resource_type = parsed.get("type")
            resource_id: str | None = parsed.get("id")

            github_repo = await self.integration.get_repository(owner, repo)

            if resource_type == "pull":
                assert resource_id is not None, "Missing PR number in URL"
                github_pr = await github_repo.get_pull_request(int(resource_id))
                pr = github_pr.pr
                return f"GitHub PR #{resource_id}: {pr.title} ({pr.state})"

            elif resource_type == "issues":
                assert resource_id is not None, "Missing issue number in URL"
                issue = await github_repo.get_issue(int(resource_id))
                return f"GitHub Issue #{resource_id}: {issue.title} ({issue.state})"

            elif resource_type == "commit":
                assert resource_id is not None, "Missing commit SHA in URL"
                commit = await github_repo.get_commit(resource_id)
                message = commit.commit.message if commit.commit else "No message"
                short_message = message.split("\n")[0][:80]
                return f"GitHub Commit {resource_id[:7]}: {short_message}"

            else:
                description = github_repo.description or "No description"
                return f"GitHub Repository {owner}/{repo}: {description}"

        except Exception as e:
            if isinstance(e, ResourceHandlingError | DescriptionGenerationError):
                raise
            logfire.error(f"Error generating GitHub description for {resource_uri}: {e}")
            raise DescriptionGenerationError(f"Failed to generate GitHub description: {e}") from e
