"""Configuration classes for external service integrations."""

from devboard.config.base import BaseConfig


class GitHubIntegrationConfig(BaseConfig):
    """Configuration for GitHub integration."""

    config_key = "integration.github.main"
    env_prefix = "GITHUB_"

    api_token: str  # From GITHUB_API_TOKEN env var
    base_url: str = "https://api.github.com"


class SlackIntegrationConfig(BaseConfig):
    """Configuration for Slack integration."""

    config_key = "integration.slack.main"
    env_prefix = "SLACK_"

    api_token: str  # From SLACK_API_TOKEN env var (Bot User OAuth Token)
    workspace_url: str | None = None  # From database (e.g., "company.slack.com")


class JiraIntegrationConfig(BaseConfig):
    """Configuration for Jira integration."""

    config_key = "integration.jira.main"
    env_prefix = "JIRA_"

    api_token: str  # From JIRA_API_TOKEN env var
    server_url: str  # From JIRA_SERVER_URL env var (e.g., "https://company.atlassian.net")
    user_email: str  # From JIRA_USER_EMAIL env var
