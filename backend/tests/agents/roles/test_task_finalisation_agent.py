"""Tests for TaskFinalisationAgentRole and finalise_task tool."""

from unittest.mock import Mock, patch

import pytest
from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.task_finalisation import TaskFinalisationAgentRole
from devboard.agents.tools.task_completion_tools import create_finalise_task_tool
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.task_service import TaskService
from tests.conftest import create_mock_task


@pytest.fixture(autouse=True)
def mock_get_execution_manager():
    """Patch get_execution_manager so role tests don't require app lifespan."""
    with patch("devboard.agents.roles.task_base.get_execution_manager") as mock:
        mock.return_value = Mock()
        yield mock


@pytest.fixture
def mock_task():
    return create_mock_task(
        task_id=1,
        title="Finalisation Task",
        status=TaskStatus.MERGED,
        specification_content="# Task Specification\n\nContent",
    )


@pytest.fixture
def mock_task_service():
    service = Mock(spec=TaskService)
    service.transition_to_complete = Mock()
    service.get_custom_fields = Mock(return_value=[])
    return service


@pytest.fixture
def mock_conversation_repo():
    repo = Mock(spec=ConversationRepository)
    repo.db = Mock()
    return repo


@pytest.fixture
def mock_document_repo():
    return Mock(spec=DocumentRepository)


@pytest.fixture
def mock_agent_config_service():
    return Mock(spec=AgentConfigService)


@pytest.fixture
def role(mock_task, mock_task_service, mock_conversation_repo, mock_document_repo, mock_agent_config_service):
    return TaskFinalisationAgentRole(
        task=mock_task,
        task_service=mock_task_service,
        working_dir="/test/working_dir",
        conversation_repo=mock_conversation_repo,
        agent_config_service=mock_agent_config_service,
        conversation_id=123,
        document_repo=mock_document_repo,
    )


class TestTaskFinalisationAgentRole:
    """Tests for TaskFinalisationAgentRole."""

    def test_role_initialization(self, role, mock_task, mock_document_repo):
        assert role.task == mock_task
        assert role.working_dir == "/test/working_dir"
        assert role.conversation_id == 123
        assert role.document_repo == mock_document_repo

    def test_get_tools_includes_common_task_tools(self, role):
        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        assert "list_tasks" in tool_names
        assert "view_task_details" in tool_names
        assert "create_task" in tool_names
        assert "investigate_codebase" in tool_names
        assert "inspect_conversation" in tool_names

    def test_get_tools_includes_finalisation_specific_tools(self, role):
        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        assert "edit_project_specification" in tool_names
        assert "finalise_task" in tool_names

    def test_get_tools_does_not_include_editing_tools(self, role):
        """Code editing tools should not be present — code is already merged."""
        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        assert "merge_branch_and_finalise" not in tool_names
        assert "merge_pr_and_finalise" not in tool_names
        assert "rebase_task_branch" not in tool_names

    def test_allowed_builtin_tools_are_read_only(self, role):
        assert role.allowed_builtin_tools == ["Read", "Grep", "Glob", "WebFetch", "WebSearch"]
        assert "Edit" not in role.allowed_builtin_tools
        assert "Bash" not in role.allowed_builtin_tools
        assert "Write" not in role.allowed_builtin_tools

    def test_include_builtin_system_prompt_is_false(self, role):
        assert role.include_builtin_system_prompt is False

    def test_system_prompt_content(self, role):
        prompt = role.get_system_prompt()
        assert "finalise_task" in prompt
        assert "project specification" in prompt.lower()

    @pytest.mark.asyncio
    async def test_get_context_content(self, role, mock_task):
        content = await role.get_context_content()
        assert isinstance(content, str)
        assert len(content) > 0


class TestCreateFinaliseTaskTool:
    """Tests for create_finalise_task_tool."""

    @pytest.fixture
    def mock_merged_task(self):
        task = Mock()
        task.id = 1
        task.status = TaskStatus.MERGED
        return task

    @pytest.fixture
    def mock_task_service(self):
        service = Mock(spec=TaskService)
        service.transition_to_complete = Mock()
        return service

    def test_tool_creation(self, mock_merged_task, mock_task_service):
        tool = create_finalise_task_tool(mock_merged_task, mock_task_service)

        assert isinstance(tool, Tool)
        assert tool.name == "finalise_task"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_transitions_merged_task_to_complete(self, mock_merged_task, mock_task_service):
        tool = create_finalise_task_tool(mock_merged_task, mock_task_service)
        result = await tool.function()

        assert "COMPLETE" in result
        mock_task_service.transition_to_complete.assert_called_once_with(mock_merged_task, method="finalise")

    @pytest.mark.asyncio
    async def test_raises_model_retry_when_not_merged(self, mock_task_service):
        for status in [TaskStatus.PLANNING, TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN, TaskStatus.COMPLETE]:
            task = Mock()
            task.id = 1
            task.status = status

            tool = create_finalise_task_tool(task, mock_task_service)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function()

            assert "MERGED" in str(exc_info.value)
            assert status.value in str(exc_info.value)

        mock_task_service.transition_to_complete.assert_not_called()
