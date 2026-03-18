"""Tests for GET /api/conversations/{id}/agent-config endpoint."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

from devboard.agents.roles import AgentRoleType
from devboard.api.dependencies.services import ExecutionServices, get_execution_services
from devboard.api.main import app
from devboard.db.models import ParentEntityType
from devboard.db.repositories import ConversationRepository


def make_mock_tool(name: str, description: str, json_schema: dict) -> Mock:
    """Create a mock PydanticAI Tool with function_schema."""
    tool = Mock()
    tool.name = name
    tool.description = description
    tool.function_schema = Mock()
    tool.function_schema.json_schema = json_schema
    return tool


def make_mock_mcp_tool(name: str, description: str, input_schema: dict, server_name: str) -> Mock:
    """Create a mock MCPTool DB model."""
    mcp_tool = Mock()
    mcp_tool.name = name
    mcp_tool.description = description
    mcp_tool.input_schema = input_schema
    mcp_tool.server = Mock()
    mcp_tool.server.name = server_name
    return mcp_tool


@contextmanager
def mock_execution_context(mock_role, agent_config, mcp_tools=None):
    """Context manager that patches create_agent_role_for_conversation and overrides get_execution_services."""
    mock_exec_services = Mock(spec=ExecutionServices)
    mock_exec_services.document_repo = Mock()
    mock_exec_services.agent_config_service = Mock()
    mock_exec_services.agent_config_service.get_agent_configuration.return_value = agent_config
    mock_exec_services.agent_config_service.get_enabled_mcp_tools.return_value = mcp_tools or []
    mock_exec_services.integration_service = Mock()
    mock_exec_services.task_service = Mock()
    mock_exec_services.task_git_service = Mock()
    mock_exec_services.conversation_repo = Mock()
    mock_exec_services.workspace_service = Mock()

    app.dependency_overrides[get_execution_services] = lambda: mock_exec_services

    try:
        with patch(
            "devboard.api.routers.conversations.create_agent_role_for_conversation",
            new=AsyncMock(return_value=mock_role),
        ):
            yield
    finally:
        del app.dependency_overrides[get_execution_services]


class TestGetAgentConfigEndpoint:
    """Tests for GET /api/conversations/{id}/agent-config endpoint."""

    def _get_task_conversation_id(self, db_session, test_task) -> int:
        conv_repo = ConversationRepository(db_session)
        conversation = conv_repo.get_active_conversation_for_entity(
            entity_type=ParentEntityType.TASK,
            entity_id=test_task.id,
        )
        assert conversation is not None
        return conversation.id

    def test_returns_404_for_nonexistent_conversation(self, client):
        """Should return 404 for a conversation that does not exist."""
        response = client.get("/api/conversations/99999/agent-config")
        assert response.status_code == 404

    def test_happy_path_returns_full_config(self, client, db_session, test_task):
        """Should return assembled agent configuration with all fields."""
        conversation_id = self._get_task_conversation_id(db_session, test_task)

        mock_role = Mock()
        mock_role.get_system_prompt.return_value = "You are a task planning assistant."
        mock_role.get_context_content = AsyncMock(return_value="# Task\nID: 1")
        mock_role.get_tools.return_value = [
            make_mock_tool(
                "set_task_specification_content",
                "Set the full content of the task specification.",
                {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]},
            )
        ]
        mock_role.allowed_builtin_tools = ["Read", "Write"]

        mock_agent_config = Mock()
        mock_agent_config.custom_instructions = "Always prefer TypeScript strict mode."

        mock_mcp_tool = make_mock_mcp_tool(
            "mcp__slack__search_channels",
            "Search Slack channels.",
            {"type": "object", "properties": {"query": {"type": "string"}}},
            "Slack",
        )

        with mock_execution_context(mock_role, mock_agent_config, mcp_tools=[mock_mcp_tool]):
            response = client.get(f"/api/conversations/{conversation_id}/agent-config")

        assert response.status_code == 200
        data = response.json()

        assert data["agent_role"] == AgentRoleType.TASK_PLANNING.value
        assert data["behaviour_guidelines"] == "You are a task planning assistant."
        assert data["context_content"] == "# Task\nID: 1"
        assert data["custom_instructions"] == "Always prefer TypeScript strict mode."

        assert data["role_tools"] == [
            {
                "name": "set_task_specification_content",
                "description": "Set the full content of the task specification.",
                "input_schema": {
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                    "required": ["content"],
                },
                "source": "role",
                "server_name": None,
            }
        ]

        assert data["mcp_tools"] == [
            {
                "name": "mcp__slack__search_channels",
                "description": "Search Slack channels.",
                "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
                "source": "mcp",
                "server_name": "Slack",
            }
        ]

        assert data["builtin_tools"] == [
            {"name": "Read", "description": None, "input_schema": None, "source": "builtin", "server_name": None},
            {"name": "Write", "description": None, "input_schema": None, "source": "builtin", "server_name": None},
        ]

    def test_null_custom_instructions(self, client, db_session, test_task):
        """Should return null for custom_instructions when none are configured."""
        conversation_id = self._get_task_conversation_id(db_session, test_task)

        mock_role = Mock()
        mock_role.get_system_prompt.return_value = "System prompt"
        mock_role.get_context_content = AsyncMock(return_value="Context")
        mock_role.get_tools.return_value = []
        mock_role.allowed_builtin_tools = []

        mock_agent_config = Mock()
        mock_agent_config.custom_instructions = None

        with mock_execution_context(mock_role, mock_agent_config):
            response = client.get(f"/api/conversations/{conversation_id}/agent-config")

        assert response.status_code == 200
        assert response.json()["custom_instructions"] is None

    def test_empty_tools(self, client, db_session, test_task):
        """Should return empty lists when no tools are configured."""
        conversation_id = self._get_task_conversation_id(db_session, test_task)

        mock_role = Mock()
        mock_role.get_system_prompt.return_value = "System prompt"
        mock_role.get_context_content = AsyncMock(return_value="Context")
        mock_role.get_tools.return_value = []
        mock_role.allowed_builtin_tools = []

        mock_agent_config = Mock()
        mock_agent_config.custom_instructions = None

        with mock_execution_context(mock_role, mock_agent_config, mcp_tools=[]):
            response = client.get(f"/api/conversations/{conversation_id}/agent-config")

        assert response.status_code == 200
        data = response.json()
        assert data["role_tools"] == []
        assert data["mcp_tools"] == []
        assert data["builtin_tools"] == []
