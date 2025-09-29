"""Jira integration for accessing tickets, projects, and comments."""

import logging
from typing import Any

from jira import JIRA as JiraClient
from jira import JIRAError

from devboard.config.integration_configs import JiraIntegrationConfig

from .base import (
    AuthenticationError,
    BaseIntegration,
    IntegrationConfigurationError,
    IntegrationConnectionResult,
    IntegrationError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


class JiraIntegration(BaseIntegration):
    """Integration for Jira API access."""

    integration_type = "jira"
    configuration_schema = JiraIntegrationConfig

    def __init__(self, config: JiraIntegrationConfig):
        """Initialize with Jira configuration and client."""
        super().__init__(config)
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

    async def test_connection(self) -> IntegrationConnectionResult:
        """Test Jira API connection."""
        try:
            user_info = self.client.myself()
            return IntegrationConnectionResult(
                success=True,
                message=f"Successfully connected to Jira as {user_info['displayName']} ({user_info['emailAddress']})",
            )
        except JIRAError as e:
            if e.status_code == 401:
                return IntegrationConnectionResult(
                    success=False, message="Jira authentication failed: Invalid credentials"
                )
            elif e.status_code == 403:
                return IntegrationConnectionResult(
                    success=False, message="Jira access forbidden: Check user permissions"
                )
            else:
                return IntegrationConnectionResult(success=False, message=f"Jira API error: {e}")

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

    async def search_issues(self, jql: str, fields: list[str] | None = None, max_results: int = 50) -> dict[str, Any]:
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
