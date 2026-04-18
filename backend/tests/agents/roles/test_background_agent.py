"""Tests for BackgroundAgentRole."""

from unittest.mock import Mock

import pytest

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.background_agent import BackgroundAgentRole
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.db.repositories.codebase import CodebaseRepository
from devboard.services.integration_service import IntegrationService
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_conversation_repo():
    repo = Mock(spec=ConversationRepository)
    db = Mock()
    repo.db = db
    return repo


@pytest.fixture
def mock_task_service():
    service = Mock(spec=TaskService)
    service.get_custom_fields.return_value = []
    return service


@pytest.fixture
def mock_codebase_repo():
    repo = Mock(spec=CodebaseRepository)
    repo.get_all.return_value = []
    return repo


@pytest.fixture
def background_role(mock_conversation_repo, mock_task_service, mock_codebase_repo):
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "devboard.agents.roles.background_agent.CodebaseRepository",
            lambda _db: mock_codebase_repo,
        )
        role = BackgroundAgentRole(
            system_prompt="Evaluate agent performance and suggest improvements.",
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
            document_repo=Mock(spec=DocumentRepository),
            agent_config_service=Mock(spec=AgentConfigService),
            integration_service=Mock(spec=IntegrationService),
        )
    return role


class TestBackgroundAgentRole:
    def test_get_system_prompt_returns_provided_prompt(self, background_role):
        prompt = background_role.get_system_prompt()

        assert prompt == "Evaluate agent performance and suggest improvements."

    def test_get_system_prompt_returns_custom_string(self, mock_conversation_repo, mock_task_service):
        custom_prompt = "You are a custom background agent with specific instructions."
        role = BackgroundAgentRole(
            system_prompt=custom_prompt,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
            document_repo=Mock(spec=DocumentRepository),
            agent_config_service=Mock(spec=AgentConfigService),
            integration_service=Mock(spec=IntegrationService),
        )

        assert role.get_system_prompt() == custom_prompt

    def test_get_tools_returns_expected_tools(self, background_role):
        tools = background_role.get_tools()

        tool_names = [t.name for t in tools]
        assert "list_conversations" in tool_names
        assert "view_conversation_details" in tool_names
        assert "view_conversation_content" in tool_names
        assert "view_agent_config" in tool_names
        assert "list_tasks" in tool_names
        assert "view_task_details" in tool_names

    def test_get_tools_returns_six_tools(self, background_role):
        tools = background_role.get_tools()

        assert len(tools) == 6

    @pytest.mark.asyncio
    async def test_get_context_content_returns_non_empty_string(self, background_role):
        content = await background_role.get_context_content()

        assert isinstance(content, str)
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_get_context_content_mentions_background_agent(self, background_role):
        content = await background_role.get_context_content()

        assert "background agent" in content.lower()
