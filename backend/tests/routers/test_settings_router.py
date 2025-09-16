"""Test settings router functionality."""

from unittest.mock import patch

import pytest

from devboard.db.models import Configuration
from devboard.db.repositories import ConfigurationRepository


@pytest.fixture
def github_config_data():
    """Valid GitHub integration configuration."""
    return {"api_token": "ghp_test_token_123", "base_url": "https://api.github.com"}


@pytest.fixture
def jira_config_data():
    """Valid Jira integration configuration."""
    return {
        "server_url": "https://company.atlassian.net",
        "user_email": "test@company.com",
        "api_token": "jira_token_123",
    }


@pytest.fixture
def openai_config_data():
    """Valid OpenAI LLM configuration."""
    return {"api_key": "sk-test-openai-key", "base_url": "https://api.openai.com/v1"}


class TestSettingsRouter:
    """Test cases for Settings Router."""

    # Integration testing endpoints

    def test_test_integration_connection_github_no_config(self, client):
        """Test GitHub integration test with no configuration."""
        response = client.post("/api/settings/integrations/github/test")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_type"] == "github"
        assert data["success"] is False
        assert data["error_type"] == "config_error"
        assert "configuration" in data["error_message"].lower()

    @patch("devboard.integrations.github.GitHubIntegration.test_connection")
    def test_test_integration_connection_github_success(self, mock_github_test, client, db_session, github_config_data):
        """Test successful GitHub integration connection."""
        # Set up configuration in database
        config_repo = ConfigurationRepository(db_session)
        config_repo.create(
            Configuration(
                key="integration.github.main",
                value_json=f'{{"api_token": "{github_config_data["api_token"]}", "base_url": "{github_config_data["base_url"]}"}}',
            )
        )
        db_session.commit()

        # Mock external GitHub API call
        mock_github_test.return_value = True

        response = client.post("/api/settings/integrations/github/test")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_type"] == "github"
        assert data["success"] is True
        assert data["error_message"] is None
        assert data["error_type"] is None

        # Verify the external call was made
        mock_github_test.assert_called_once()

    @patch("devboard.integrations.github.GitHubIntegration.test_connection")
    def test_test_integration_connection_github_api_failure(
        self, mock_github_test, client, db_session, github_config_data
    ):
        """Test GitHub integration with API connection failure."""
        # Set up valid configuration
        config_repo = ConfigurationRepository(db_session)
        config_repo.create(
            Configuration(
                key="integration.github.main",
                value_json=f'{{"api_token": "{github_config_data["api_token"]}", "base_url": "{github_config_data["base_url"]}"}}',
            )
        )
        db_session.commit()

        # Mock external API failure
        from devboard.integrations.base import ConnectionError

        mock_github_test.side_effect = ConnectionError("API connection failed")

        response = client.post("/api/settings/integrations/github/test")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_type"] == "github"
        assert data["success"] is False
        assert data["error_type"] == "connection_error"
        assert "API connection failed" in data["error_message"]

    @patch("devboard.integrations.jira.JiraIntegration.test_connection")
    def test_test_integration_connection_jira_success(self, mock_jira_test, client, db_session, jira_config_data):
        """Test successful Jira integration connection."""
        # Set up configuration
        config_repo = ConfigurationRepository(db_session)
        config_repo.create(
            Configuration(
                key="integration.jira.main",
                value_json=f'{{"server_url": "{jira_config_data["server_url"]}", "user_email": "{jira_config_data["user_email"]}", "api_token": "{jira_config_data["api_token"]}"}}',
            )
        )
        db_session.commit()

        # Mock external Jira API call
        mock_jira_test.return_value = True

        response = client.post("/api/settings/integrations/jira/test")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_type"] == "jira"
        assert data["success"] is True
        assert data["error_message"] is None

    def test_test_integration_connection_unsupported(self, client):
        """Test integration connection test with unsupported integration type."""
        response = client.post("/api/settings/integrations/unknown/test")

        assert response.status_code == 404
        data = response.json()
        assert "unknown" in data["detail"].lower()

    def test_test_integration_connection_slack_no_config(self, client):
        """Test Slack integration with no configuration."""
        response = client.post("/api/settings/integrations/slack/test")

        assert response.status_code == 200
        data = response.json()
        assert data["integration_type"] == "slack"
        assert data["success"] is False
        assert data["error_type"] == "config_error"
