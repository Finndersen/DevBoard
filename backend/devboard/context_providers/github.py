"""GitHub context provider for PR, issue, and repository context."""

import logging
import re
from typing import Any
from urllib.parse import urlparse

from devboard.integrations.github import GitHubIntegration

from .base import (
    BaseContextProvider,
    ContextProviderUnavailable,
    ContextRetrievalError,
    ContextStrategy,
    DescriptionGenerationError,
    ResourceHandlingError,
)

logger = logging.getLogger(__name__)


class GitHubContextProvider(BaseContextProvider):
    """Context provider for GitHub resources (PRs, issues, commits, repositories)."""

    provider_type = "github"

    @classmethod
    def create_instance(cls) -> "GitHubContextProvider":
        """Create an instance of the GitHub context provider.

        Validates configuration and creates the GitHub integration.

        Returns:
            Configured GitHubContextProvider instance

        Raises:
            ContextProviderUnavailable: If GitHub configuration is missing or invalid
        """
        from devboard.core.config import config_service

        config_result = config_service.validate_config("integration.github.main")
        if not config_result.success or not config_result.config:
            raise ContextProviderUnavailable(
                f"GitHub integration not configured: {config_result.errors}"
            )

        try:
            integration = GitHubIntegration(config_result.config)
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

        Small-scope resources (single issues, PRs, commits, files) are EAGER.
        Large-scope resources (entire repos, searches) are ON_DEMAND.
        """
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        parsed = self._parse_github_url(resource_uri)
        if not parsed:
            return ContextStrategy.ON_DEMAND

        resource_type = parsed.get("type")

        # Small-scope resources that can be loaded eagerly
        if resource_type in ("pull", "issues", "commit", "blob", "tree"):
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

    async def get_resource(self, resource_uri: str) -> dict[str, Any]:
        """Get full resource data for EAGER strategy (small-scope resources)."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            parsed = self._parse_github_url(resource_uri)
            if not parsed:
                raise ResourceHandlingError(f"Invalid GitHub URL format: {resource_uri}")

            owner, repo = parsed["owner"], parsed["repo"]
            resource_type = parsed.get("type")
            resource_id = parsed.get("id")

            # Load full data for small-scope resources
            if resource_type == "pull":
                pr_data = await self.integration.get_pull_request(owner, repo, int(resource_id))
                return {"type": "pull_request", "data": pr_data, "uri": resource_uri}
            elif resource_type == "issues":
                issue_data = await self.integration.get_issue(owner, repo, int(resource_id))
                return {"type": "issue", "data": issue_data, "uri": resource_uri}
            elif resource_type == "commit":
                commit_data = await self.integration.get_commit(owner, repo, resource_id)
                return {"type": "commit", "data": commit_data, "uri": resource_uri}
            elif resource_type in ("blob", "tree"):
                file_data = await self.integration.get_file_content(owner, repo, resource_id)
                return {"type": "file", "data": file_data, "uri": resource_uri}
            else:
                raise ContextRetrievalError(
                    f"Unsupported resource type for EAGER loading: {resource_type}"
                )

        except Exception as e:
            if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                raise
            logger.error(f"Error getting GitHub resource for {resource_uri}: {e}")
            raise ContextRetrievalError(f"Failed to get GitHub resource: {e}") from e

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        """Get query-relevant context from GitHub resource."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            parsed = self._parse_github_url(resource_uri)
            if not parsed:
                raise ResourceHandlingError(f"Invalid GitHub URL format: {resource_uri}")

            owner, repo = parsed["owner"], parsed["repo"]
            resource_type = parsed.get("type")
            resource_id = parsed.get("id")

            # Fetch appropriate data based on resource type
            if resource_type == "pull":
                if not resource_id:
                    raise ResourceHandlingError("Missing PR number in URL")
                pr_data = await self.integration.get_pull_request(owner, repo, int(resource_id))

                # Create focused summary based on query
                context = f"""
GitHub Pull Request: {pr_data.get("title", "No title")}
URL: {resource_uri}
Status: {pr_data.get("state", "unknown")}
Author: {pr_data.get("user", {}).get("login", "unknown")}
Description: {pr_data.get("body", "No description")}

Query: {query}

Based on this PR data and comments, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                return context

            elif resource_type == "issues":
                if not resource_id:
                    raise ResourceHandlingError("Missing issue number in URL")
                issue_data = await self.integration.get_issue(owner, repo, int(resource_id))

                context = f"""
GitHub Issue: {issue_data.get("title", "No title")}
URL: {resource_uri}
Status: {issue_data.get("state", "unknown")}
Author: {issue_data.get("user", {}).get("login", "unknown")}
Description: {issue_data.get("body", "No description")}

Query: {query}

Based on this issue data, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                return context

            elif resource_type == "commit":
                if not resource_id:
                    raise ResourceHandlingError("Missing commit SHA in URL")
                commit_data = await self.integration.get_commit(owner, repo, resource_id)

                context = f"""
GitHub Commit: {commit_data.get("commit", {}).get("message", "No message")}
URL: {resource_uri}
Author: {commit_data.get("commit", {}).get("author", {}).get("name", "unknown")}
SHA: {resource_id}

Query: {query}

Based on this commit data, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                return context

            else:
                # Repository-level resource
                repo_data = await self.integration.get_repository(owner, repo)

                context = f"""
GitHub Repository: {repo_data.get("full_name", "unknown")}
URL: {resource_uri}
Description: {repo_data.get("description", "No description")}
Language: {repo_data.get("language", "unknown")}

Query: {query}

Based on this repository data, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                return context

        except Exception as e:
            if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                raise
            logger.error(f"Error getting GitHub context for {resource_uri}: {e}")
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
            resource_id = parsed.get("id")

            if resource_type == "pull":
                pr_data = await self.integration.get_pull_request(owner, repo, int(resource_id))
                return f"GitHub PR #{resource_id}: {pr_data.get('title', 'No title')} ({pr_data.get('state', 'unknown')})"

            elif resource_type == "issues":
                issue_data = await self.integration.get_issue(owner, repo, int(resource_id))
                return f"GitHub Issue #{resource_id}: {issue_data.get('title', 'No title')} ({issue_data.get('state', 'unknown')})"

            elif resource_type == "commit":
                commit_data = await self.integration.get_commit(owner, repo, resource_id)
                message = commit_data.get("commit", {}).get("message", "No message")
                short_message = message.split("\n")[0][:80]
                return f"GitHub Commit {resource_id[:7]}: {short_message}"

            else:
                repo_data = await self.integration.get_repository(owner, repo)
                description = repo_data.get("description", "No description")
                return f"GitHub Repository {owner}/{repo}: {description}"

        except Exception as e:
            if isinstance(e, ResourceHandlingError | DescriptionGenerationError):
                raise
            logger.error(f"Error generating GitHub description for {resource_uri}: {e}")
            raise DescriptionGenerationError(f"Failed to generate GitHub description: {e}") from e
