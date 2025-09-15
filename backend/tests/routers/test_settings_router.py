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
        mock_github_test.side_effect = Exception("API connection failed")

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

    # Agent models endpoints

    def test_get_available_models_no_config(self, client):
        """Test getting available models with no LLM configurations."""
        response = client.get("/api/settings/agents/available-models")

        assert response.status_code == 200
        data = response.json()

        # Should return structure for all agent types even without config
        assert "qa" in data or "planning" in data or "implementation" in data

        # Each agent type should have available_models list
        for agent_data in data.values():
            if agent_data:  # Skip None values
                assert "available_models" in agent_data
                assert "total_available" in agent_data
                assert isinstance(agent_data["available_models"], list)

    def test_get_available_models_with_openai_config(self, client, db_session, openai_config_data):
        """Test getting available models with OpenAI configuration."""
        # Set up OpenAI configuration
        config_repo = ConfigurationRepository(db_session)
        config_repo.create(
            Configuration(
                key="llm.openai.main",
                value_json=f'{{"api_key": "{openai_config_data["api_key"]}", "base_url": "{openai_config_data["base_url"]}"}}',
            )
        )
        db_session.commit()

        response = client.get("/api/settings/agents/available-models")

        assert response.status_code == 200
        data = response.json()

        # Should include OpenAI models in the available models
        for agent_data in data.values():
            if agent_data and agent_data.get("available_models"):
                # Should have some models available
                assert len(agent_data["available_models"]) > 0

                # Check that models have required fields
                for model in agent_data["available_models"]:
                    assert "id" in model
                    assert "provider" in model
                    assert "name" in model

    def test_get_available_models_specific_agent_type(self, client):
        """Test getting available models for specific agent type."""
        response = client.get("/api/settings/agents/available-models?agent_type=planning")

        assert response.status_code == 200
        data = response.json()

        assert data["agent_type"] == "planning"
        assert "available_models" in data
        assert "preferred_model" in data
        assert "total_available" in data
        assert isinstance(data["available_models"], list)

    def test_get_available_models_invalid_agent_type(self, client):
        """Test getting available models with invalid agent type."""
        response = client.get("/api/settings/agents/available-models?agent_type=invalid")

        assert response.status_code == 400
        data = response.json()
        assert "Unknown agent type" in data["detail"]
        assert "invalid" in data["detail"]

        # Should list valid API agent types (API-friendly names)
        expected_valid_types = ["qa", "planning", "implementation"]
        for agent_type in expected_valid_types:
            assert agent_type in data["detail"]

    def test_get_available_models_all_agent_types(self, client):
        """Test getting available models returns data for all supported agent types."""
        response = client.get("/api/settings/agents/available-models")

        assert response.status_code == 200
        data = response.json()

        # Should have some agent types in the response
        agent_types_in_response = [key for key, value in data.items() if value is not None]
        assert len(agent_types_in_response) > 0

        # Each non-null entry should have the expected structure
        for agent_type, agent_data in data.items():
            if agent_data is not None:
                assert "available_models" in agent_data
                assert "total_available" in agent_data
                assert isinstance(agent_data["available_models"], list)
                assert isinstance(agent_data["total_available"], int)

    def test_end_to_end_integration_workflow(self, client, db_session):
        """Test complete integration setup and testing workflow."""
        # 1. Test integration without configuration (should fail)
        response = client.post("/api/settings/integrations/github/test")
        assert response.status_code == 200
        assert response.json()["success"] is False

        # 2. Add configuration
        config_repo = ConfigurationRepository(db_session)
        config_repo.create(
            Configuration(
                key="integration.github.main",
                value_json='{"api_token": "ghp_test_token", "base_url": "https://api.github.com"}',
            )
        )
        db_session.commit()

        # 3. Test integration with configuration (would make external call)
        with patch("devboard.integrations.github.GitHubIntegration.test_connection", return_value=True):
            response = client.post("/api/settings/integrations/github/test")
            assert response.status_code == 200
            assert response.json()["success"] is True

        # 4. Test models availability (should show available models)
        response = client.get("/api/settings/agents/available-models")
        assert response.status_code == 200
        data = response.json()

        # Should have agent type data
        agent_types = [k for k, v in data.items() if v is not None]
        assert len(agent_types) > 0
