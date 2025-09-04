"""Jira integration for accessing tickets, projects, and comments."""

import logging
from typing import Any

from jira import JIRA as JiraClient
from jira import JIRAError

from devboard.config.base import BaseConfig

from .base import (
    AuthenticationError,
    BaseIntegration,
    IntegrationConfigurationError,
    IntegrationError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


class JiraIntegrationConfig(BaseConfig):
    """Configuration for Jira integration."""

    config_key = "integration.jira.main"

    api_token: str  # From JIRA_API_TOKEN env var
    server_url: str  # From JIRA_SERVER_URL env var (e.g., "https://company.atlassian.net")
    user_email: str  # From JIRA_USER_EMAIL env var

    model_config = BaseConfig.get_base_config("JIRA_")


class JiraIntegration(BaseIntegration):
    """Integration for Jira API access."""

    integration_type = "jira"

    def __init__(self, config: JiraIntegrationConfig):
        """Initialize with Jira configuration and client."""
        self.config = config
        try:
            self.client = JiraClient(
                server=config.server_url,
                basic_auth=(config.user_email, config.api_token),
                options={"agile_rest_path": "agile"},
            )
            logger.info("Initialized Jira integration")
        except Exception as e:
            logger.error(f"Failed to initialize Jira integration: {e}")
            raise IntegrationConfigurationError(f"Failed to initialize Jira: {e}") from e

    @classmethod
    async def create(cls) -> "JiraIntegration":
        """Create Jira integration instance with configuration from environment."""
        try:
            config = JiraIntegrationConfig()
            return cls(config)
        except Exception as e:
            logger.error(f"Failed to create Jira integration: {e}")
            raise IntegrationConfigurationError(f"Jira configuration error: {e}") from e

    async def test_connection(self) -> bool:
        """Test Jira API connection."""
        try:
            self.client.myself()
            return True
        except Exception as e:
            logger.error(f"Jira connection test failed: {e}")
            return False

    async def get_issue(self, issue_key: str, fields: list[str] | None = None) -> dict[str, Any]:
        """Get details of a specific Jira issue."""
        try:
            expand = None
            if fields:
                expand = ",".join(fields)

            issue = self.client.issue(issue_key, expand=expand)
            return issue.raw  # type: ignore[return-value]
        except JIRAError as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(f"Jira authentication failed: {e}") from e
            elif "404" in str(e):
                raise ResourceNotFoundError(f"Issue {issue_key} not found: {e}") from e
            else:
                logger.error(f"Jira error in get_issue({issue_key}): {e}")
                raise IntegrationError(f"Jira error: {e}") from e

    async def get_project(self, project_key: str) -> dict[str, Any]:
        """Get details of a Jira project."""
        try:
            project = self.client.project(project_key)
            return project.raw  # type: ignore[return-value]
        except JIRAError as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(f"Jira authentication failed: {e}") from e
            elif "404" in str(e):
                raise ResourceNotFoundError(f"Project {project_key} not found: {e}") from e
            else:
                logger.error(f"Jira error in get_project({project_key}): {e}")
                raise IntegrationError(f"Jira error: {e}") from e

    async def search_issues(
        self, jql: str, fields: list[str] | None = None, max_results: int = 50
    ) -> dict[str, Any]:
        """Search issues using JQL."""
        try:
            issues = self.client.search_issues(jql, maxResults=max_results, fields=fields)

            # Convert to dict format similar to REST API response
            return {
                "issues": [issue.raw for issue in issues],
                "total": len(issues),
                "maxResults": max_results,
            }
        except JIRAError as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(f"Jira authentication failed: {e}") from e
            else:
                logger.error(f"Jira error in search_issues({jql}): {e}")
                raise IntegrationError(f"Jira error: {e}") from e

    async def get_issue_comments(self, issue_key: str) -> list[dict[str, Any]]:
        """Get comments for a Jira issue."""
        try:
            comments = self.client.comments(issue_key)
            return [comment.raw for comment in comments]  # type: ignore[return-value]
        except JIRAError as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(f"Jira authentication failed: {e}") from e
            elif "404" in str(e):
                raise ResourceNotFoundError(f"Issue {issue_key} not found: {e}") from e
            else:
                logger.error(f"Jira error in get_issue_comments({issue_key}): {e}")
                raise IntegrationError(f"Jira error: {e}") from e

    async def update_issue(self, issue_key: str, fields: dict[str, Any]) -> None:
        """Update a Jira issue."""
        try:
            issue = self.client.issue(issue_key)
            issue.update(fields=fields)
        except JIRAError as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(f"Jira authentication failed: {e}") from e
            elif "404" in str(e):
                raise ResourceNotFoundError(f"Issue {issue_key} not found: {e}") from e
            else:
                logger.error(f"Jira error in update_issue({issue_key}): {e}")
                raise IntegrationError(f"Jira error: {e}") from e

    async def add_comment(self, issue_key: str, comment_body: str) -> dict[str, Any]:
        """Add a comment to a Jira issue."""
        try:
            comment = self.client.add_comment(issue_key, comment_body)
            return comment.raw  # type: ignore[return-value]
        except JIRAError as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(f"Jira authentication failed: {e}") from e
            elif "404" in str(e):
                raise ResourceNotFoundError(f"Issue {issue_key} not found: {e}") from e
            else:
                logger.error(f"Jira error in add_comment({issue_key}): {e}")
                raise IntegrationError(f"Jira error: {e}") from e

    async def get_transitions(self, issue_key: str) -> list[dict[str, Any]]:
        """Get available transitions for an issue."""
        try:
            transitions = self.client.transitions(issue_key)
            return transitions  # type: ignore[return-value]
        except JIRAError as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(f"Jira authentication failed: {e}") from e
            elif "404" in str(e):
                raise ResourceNotFoundError(f"Issue {issue_key} not found: {e}") from e
            else:
                logger.error(f"Jira error in get_transitions({issue_key}): {e}")
                raise IntegrationError(f"Jira error: {e}") from e

    async def transition_issue(self, issue_key: str, transition_id: str) -> None:
        """Transition a Jira issue to a new status."""
        try:
            self.client.transition_issue(issue_key, transition_id)
        except JIRAError as e:
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(f"Jira authentication failed: {e}") from e
            elif "404" in str(e):
                raise ResourceNotFoundError(f"Issue {issue_key} not found: {e}") from e
            else:
                logger.error(f"Jira error in transition_issue({issue_key}): {e}")
                raise IntegrationError(f"Jira error: {e}") from e

    @staticmethod
    def parse_issue_url(url: str) -> str | None:
        """Extract issue key from Jira URL."""
        # Handle URLs like: https://company.atlassian.net/browse/PROJ-123
        if "/browse/" in url:
            return url.split("/browse/")[1].split("?")[0]
        return None
