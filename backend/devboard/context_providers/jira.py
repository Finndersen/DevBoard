"""Jira context provider for ticket, project, and comment context."""

import logging
import re
from typing import Any
from urllib.parse import urlparse

from devboard.integrations.jira import JiraIntegration

from .base import (
    BaseContextProvider,
    ContextProviderUnavailable,
    ContextRetrievalError,
    ContextStrategy,
    DescriptionGenerationError,
    ResourceHandlingError,
)

logger = logging.getLogger(__name__)


class JiraContextProvider(BaseContextProvider):
    """Context provider for Jira resources (issues, projects, comments)."""

    provider_type = "jira"

    @classmethod
    def create_instance(cls) -> "JiraContextProvider":
        """Create an instance of the Jira context provider.

        Uses JiraIntegration.create() to handle configuration validation and initialization.

        Returns:
            Configured JiraContextProvider instance

        Raises:
            ContextProviderUnavailable: If Jira configuration is missing or invalid
        """
        try:
            integration = JiraIntegration.create()
            return cls(integration)
        except Exception as e:
            raise ContextProviderUnavailable(f"Failed to initialize Jira integration: {e}") from e

    def __init__(self, integration: JiraIntegration):
        """Initialize with Jira integration."""
        self.integration = integration

    @classmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        """Check if URI is a Jira resource."""
        parsed = urlparse(resource_uri)
        return "atlassian.net" in parsed.netloc or "/browse/" in resource_uri

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        """Jira resources can be EAGER for single issues, ON_DEMAND for projects."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        # Single issues are small enough for EAGER loading
        if "/browse/" in resource_uri:
            return ContextStrategy.EAGER
        # Projects and searches are ON_DEMAND
        return ContextStrategy.ON_DEMAND

    def _parse_jira_url(self, url: str) -> dict[str, str] | None:
        """Parse Jira URL to extract components."""
        try:
            # Handle URLs like:
            # https://company.atlassian.net/browse/PROJ-123
            # https://company.atlassian.net/projects/PROJ

            if "/browse/" in url:
                issue_key = JiraIntegration.parse_issue_url(url)
                if issue_key:
                    return {"type": "issue", "key": issue_key}

            # Extract project key from various URL formats
            project_match = re.search(r"/projects/([A-Z]+)", url)
            if project_match:
                return {"type": "project", "key": project_match.group(1)}

            return None
        except Exception:
            return None

    async def get_resource(self, resource_uri: str) -> dict[str, Any]:
        """Get full resource data for EAGER strategy (single issues)."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            parsed = self._parse_jira_url(resource_uri)
            if not parsed:
                raise ResourceHandlingError(f"Invalid Jira URL format: {resource_uri}")

            if parsed["type"] == "issue":
                issue_data = await self.integration.get_issue(parsed["key"])
                comments_data = await self.integration.get_issue_comments(parsed["key"])

                return {"issue": issue_data, "comments": comments_data, "uri": resource_uri}
            else:
                raise ResourceHandlingError("get_resource only supports individual issues")

        except Exception as e:
            if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                raise
            logger.error(f"Error getting Jira resource for {resource_uri}: {e}")
            raise ContextRetrievalError(f"Failed to get Jira resource: {e}") from e

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        """Get query-relevant context from Jira resource."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            parsed = self._parse_jira_url(resource_uri)
            if not parsed:
                raise ResourceHandlingError(f"Invalid Jira URL format: {resource_uri}")

            if parsed["type"] == "issue":
                issue_data = await self.integration.get_issue(parsed["key"])
                comments_data = await self.integration.get_issue_comments(parsed["key"])

                # Extract key fields from Jira issue
                fields = issue_data.get("fields", {})
                context = f"""
Jira Issue: {fields.get("summary", "No title")}
Key: {parsed["key"]}
URL: {resource_uri}
Status: {fields.get("status", {}).get("name", "unknown")}
Assignee: {fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned"}
Priority: {fields.get("priority", {}).get("name", "unknown") if fields.get("priority") else "unknown"}
Description: {fields.get("description", "No description")}

Comments: {len(comments_data)} comments available

Query: {query}

Based on this Jira issue data, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                return context

            elif parsed["type"] == "project":
                project_data = await self.integration.get_project(parsed["key"])

                context = f"""
Jira Project: {project_data.get("name", "Unknown Project")}
Key: {parsed["key"]}
URL: {resource_uri}
Description: {project_data.get("description", "No description")}

Query: {query}

Based on this project data, here is the relevant context for your query:
[This would be processed by an AI agent to extract query-relevant information]
"""
                return context
            else:
                raise ResourceHandlingError(f"Unsupported Jira resource type: {parsed.get('type')}")

        except Exception as e:
            if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                raise
            logger.error(f"Error getting Jira context for {resource_uri}: {e}")
            raise ContextRetrievalError(f"Failed to get Jira context: {e}") from e

    async def generate_resource_description(self, resource_uri: str) -> str:
        """Generate description for Jira resource."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            parsed = self._parse_jira_url(resource_uri)
            if not parsed:
                raise ResourceHandlingError(f"Invalid Jira URL format: {resource_uri}")

            if parsed["type"] == "issue":
                issue_data = await self.integration.get_issue(parsed["key"])
                fields = issue_data.get("fields", {})
                status = fields.get("status", {}).get("name", "unknown")
                return f"Jira Issue {parsed['key']}: {fields.get('summary', 'No title')} ({status})"

            elif parsed["type"] == "project":
                project_data = await self.integration.get_project(parsed["key"])
                return f"Jira Project {parsed['key']}: {project_data.get('name', 'Unknown Project')}"
            else:
                return f"Jira Resource: {parsed['key']}"

        except Exception as e:
            if isinstance(e, ResourceHandlingError | DescriptionGenerationError):
                raise
            logger.error(f"Error generating Jira description for {resource_uri}: {e}")
            raise DescriptionGenerationError(f"Failed to generate Jira description: {e}") from e
