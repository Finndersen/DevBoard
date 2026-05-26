"""Tests for BackgroundAgentRole."""

from unittest.mock import Mock, patch

import pytest

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.background_agent import BackgroundAgentRole
from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.models.codebase import Codebase
from devboard.db.repositories import (
    BackgroundAgentRepository,
    BackgroundAgentRunRepository,
    ConversationRepository,
    DocumentRepository,
)
from devboard.db.repositories.codebase import CodebaseRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.services.integration_service import IntegrationService
from devboard.services.log_entry_service import LogEntryService
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
def mock_project_repo():
    repo = Mock(spec=ProjectRepository)
    return repo


@pytest.fixture
def mock_background_agent():
    agent = Mock(spec=BackgroundAgent)
    agent.id = 1
    return agent


@pytest.fixture
def mock_log_entry_service():
    return Mock(spec=LogEntryService)


@pytest.fixture
def mock_background_agent_repo():
    return Mock(spec=BackgroundAgentRepository)


@pytest.fixture
def mock_agent_run_repo():
    return Mock(spec=BackgroundAgentRunRepository)


@pytest.fixture
def background_role(
    mock_conversation_repo,
    mock_task_service,
    mock_codebase_repo,
    mock_project_repo,
    mock_background_agent,
    mock_log_entry_service,
    mock_background_agent_repo,
    mock_agent_run_repo,
):
    return BackgroundAgentRole(
        system_prompt="Evaluate agent performance and suggest improvements.",
        task_service=mock_task_service,
        conversation_repo=mock_conversation_repo,
        document_repo=Mock(spec=DocumentRepository),
        agent_config_service=Mock(spec=AgentConfigService),
        integration_service=Mock(spec=IntegrationService),
        project_repo=mock_project_repo,
        codebase_repo=mock_codebase_repo,
        background_agent=mock_background_agent,
        conversation_id=None,
        log_entry_service=mock_log_entry_service,
        background_agent_repo=mock_background_agent_repo,
        agent_run_repo=mock_agent_run_repo,
    )


class TestBackgroundAgentRole:
    def test_get_system_prompt_returns_provided_prompt(self, background_role):
        prompt = background_role.get_system_prompt()

        assert prompt == "Evaluate agent performance and suggest improvements."

    def test_get_system_prompt_returns_custom_string(
        self,
        mock_conversation_repo,
        mock_task_service,
        mock_codebase_repo,
        mock_project_repo,
        mock_background_agent,
        mock_log_entry_service,
        mock_background_agent_repo,
        mock_agent_run_repo,
    ):
        custom_prompt = "You are a custom background agent with specific instructions."
        role = BackgroundAgentRole(
            system_prompt=custom_prompt,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
            document_repo=Mock(spec=DocumentRepository),
            agent_config_service=Mock(spec=AgentConfigService),
            integration_service=Mock(spec=IntegrationService),
            project_repo=mock_project_repo,
            codebase_repo=mock_codebase_repo,
            background_agent=mock_background_agent,
            conversation_id=None,
            log_entry_service=mock_log_entry_service,
            background_agent_repo=mock_background_agent_repo,
            agent_run_repo=mock_agent_run_repo,
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
        assert "list_projects" in tool_names
        assert "view_project_details" in tool_names
        assert "edit_project_specification" in tool_names
        assert "set_project_specification_content" in tool_names
        assert "query_events" in tool_names
        assert "create_event" in tool_names
        assert "read_state" in tool_names
        assert "update_state" in tool_names
        assert "read_agent_state" in tool_names
        assert "query_agent_runs" in tool_names

    def test_get_tools_returns_seventeen_tools_without_codebases(self, background_role):
        tools = background_role.get_tools()

        assert len(tools) == 17

    def test_get_tools_includes_codebase_tools_when_codebases_exist(
        self,
        mock_conversation_repo,
        mock_task_service,
        mock_project_repo,
        mock_background_agent,
        mock_log_entry_service,
        mock_background_agent_repo,
        mock_agent_run_repo,
    ):
        mock_codebase = Mock(spec=Codebase)
        mock_codebase.name = "test-codebase"
        mock_codebase.local_path = "/tmp/test"
        mock_codebase_repo = Mock(spec=CodebaseRepository)
        mock_codebase_repo.get_all.return_value = [mock_codebase]
        role = BackgroundAgentRole(
            system_prompt="Test prompt.",
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
            document_repo=Mock(spec=DocumentRepository),
            agent_config_service=Mock(spec=AgentConfigService),
            integration_service=Mock(spec=IntegrationService),
            project_repo=mock_project_repo,
            codebase_repo=mock_codebase_repo,
            background_agent=mock_background_agent,
            conversation_id=42,
            log_entry_service=mock_log_entry_service,
            background_agent_repo=mock_background_agent_repo,
            agent_run_repo=mock_agent_run_repo,
        )

        with patch("devboard.agents.roles.background_agent.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            tools = role.get_tools()

        tool_names = [t.name for t in tools]
        assert "view_codebase_details" in tool_names
        assert "investigate_codebase" in tool_names
        assert len(tools) == 19

    @pytest.mark.asyncio
    async def test_get_context_content_returns_non_empty_string(self, background_role):
        content = await background_role.get_context_content()

        assert isinstance(content, str)
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_get_context_content_mentions_background_agent(self, background_role):
        content = await background_role.get_context_content()

        assert "background agent" in content.lower()
