"""Tests for create_task tool functionality."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.task_tools import create_create_task_tool
from devboard.db.models import Codebase, Conversation, Project, Task, TaskStatus
from devboard.db.repositories.conversation import ConversationRepository
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_codebase():
    codebase = Mock(spec=Codebase)
    codebase.id = 10
    codebase.name = "backend"
    codebase.default_branch = "main"
    return codebase


@pytest.fixture
def mock_project(mock_codebase):
    project = Mock(spec=Project)
    project.id = 1
    project.name = "Test Project"
    project.codebases = [mock_codebase]
    return project


@pytest.fixture
def mock_task(mock_codebase):
    task = Mock(spec=Task)
    task.id = 42
    task.project_id = 1
    task.title = "New Task"
    task.status = TaskStatus.PLANNING
    task.branch_name = "new-task"
    task.base_branch = "main"
    task.codebase = mock_codebase
    task.specification = Mock()
    task.specification.content = "Some spec content"
    task.implementation_plan = None
    task.implementation_plan_structured = None
    return task


@pytest.fixture
def mock_task_service(mock_task):
    service = Mock(spec=TaskService)
    service.get_custom_fields.return_value = []
    service.get_mandatory_custom_fields.return_value = []
    service.create_task = AsyncMock(return_value=mock_task)
    return service


@pytest.fixture
def mock_conversation_repo():
    repo = Mock(spec=ConversationRepository)
    conversation = Mock(spec=Conversation)
    conversation.id = 99
    repo.get_active_conversation_for_entity.return_value = conversation
    return repo


class TestCreateTaskInitialPrompt:
    """Tests for create_task tool initial_prompt parameter."""

    @pytest.mark.asyncio
    async def test_initial_prompt_without_conversation_repo_raises_model_retry(self, mock_project, mock_task_service):
        """initial_prompt without conversation_repo raises ModelRetry before creating task."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=None,
        )

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(
                title="New Task",
                codebase_name="backend",
                initial_prompt="Investigate and write the spec",
            )

        assert "initial_prompt is not supported in this context" in str(exc_info.value)
        mock_task_service.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_initial_prompt_starts_execution_with_given_prompt(
        self, mock_project, mock_task_service, mock_conversation_repo, mock_task
    ):
        """initial_prompt starts execution with the provided prompt string."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
        )

        with patch("devboard.agents.tools.task_tools.get_execution_manager") as mock_get_mgr:
            mock_exec_manager = Mock()
            mock_get_mgr.return_value = mock_exec_manager
            await tool.function(
                title="New Task",
                codebase_name="backend",
                initial_prompt="Investigate and write the spec",
            )

        mock_exec_manager.start_agent_execution.assert_called_once_with(
            99,
            "Investigate and write the spec",
        )

    @pytest.mark.asyncio
    async def test_initial_prompt_returns_conversation_id(
        self, mock_project, mock_task_service, mock_conversation_repo, mock_task
    ):
        """initial_prompt causes active_conversation_id to be included in response."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
        )

        with patch("devboard.agents.tools.task_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            result = await tool.function(
                title="New Task",
                codebase_name="backend",
                initial_prompt="The spec is complete. Create the implementation plan.",
            )

        result_data = json.loads(result)
        assert result_data["task_id"] == mock_task.id
        assert result_data["active_conversation_id"] == 99

    @pytest.mark.asyncio
    async def test_initial_prompt_none_does_not_start_execution(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """initial_prompt=None (default) does not start any execution."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
        )

        with patch("devboard.agents.tools.task_tools.get_execution_manager") as mock_get_mgr:
            mock_exec_manager = Mock()
            mock_get_mgr.return_value = mock_exec_manager
            result = await tool.function(
                title="New Task",
                codebase_name="backend",
            )

        result_data = json.loads(result)
        assert "active_conversation_id" not in result_data
        mock_exec_manager.start_agent_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_initial_prompt_without_specification_content_works(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """initial_prompt does not require specification_content."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
        )

        with patch("devboard.agents.tools.task_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            # Should not raise
            result = await tool.function(
                title="New Task",
                codebase_name="backend",
                initial_prompt="Investigate the codebase and write the spec",
            )

        result_data = json.loads(result)
        assert result_data["task_id"] == 42
        assert result_data["active_conversation_id"] == 99

    @pytest.mark.asyncio
    async def test_initial_prompt_with_specification_content_works(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """initial_prompt and specification_content can be provided together."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
        )

        with patch("devboard.agents.tools.task_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            result = await tool.function(
                title="New Task",
                codebase_name="backend",
                specification_content="Detailed spec content",
                initial_prompt="The spec is complete. Create the implementation plan.",
            )

        result_data = json.loads(result)
        assert result_data["task_id"] == 42
        assert result_data["active_conversation_id"] == 99

    def test_initial_prompt_field_in_json_schema(self, mock_project, mock_task_service):
        """initial_prompt field appears in the JSON schema with correct type and default."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
        )
        schema = tool.tool_def.parameters_json_schema
        props = schema["properties"]

        assert "initial_prompt" in props
        assert "auto_plan" not in props
        initial_prompt_schema = props["initial_prompt"]
        assert initial_prompt_schema["default"] is None
        assert {"type": "string"} in initial_prompt_schema["anyOf"]
        assert {"type": "null"} in initial_prompt_schema["anyOf"]


class TestCreateTaskBranchCreation:
    """Tests for git branch creation when creating a task via the tool."""

    @pytest.mark.asyncio
    async def test_creates_task_and_returns_task_id(self, mock_project, mock_task_service, mock_task):
        """Branch creation is now handled inside TaskService.create_task."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
        )

        result = await tool.function(title="New Task", codebase_name="backend")

        mock_task_service.create_task.assert_called_once()
        result_data = json.loads(result)
        assert result_data["task_id"] == mock_task.id

    @pytest.mark.asyncio
    async def test_task_service_failure_raises_model_retry(self, mock_project, mock_task_service):
        """Service errors (including branch failures) wrap into ModelRetry."""
        mock_task_service.create_task.side_effect = ValueError("git error")

        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
        )

        with pytest.raises(ModelRetry, match="Failed to create task"):
            await tool.function(title="New Task", codebase_name="backend")


class TestCreateTaskMandatoryCustomFields:
    """Tests for mandatory custom field validation in create_task tool.

    Validation is now performed inside TaskService.create_task, so errors surface
    as ModelRetry wrapping the ValueError raised by the service.
    """

    @pytest.mark.asyncio
    async def test_missing_mandatory_fields_raises_model_retry(self, mock_project, mock_task_service):
        mock_task_service.create_task.side_effect = ValueError("Missing required custom fields: priority")

        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
        )

        with pytest.raises(ModelRetry, match="Missing required custom fields: priority"):
            await tool.function(title="New Task", codebase_name="backend")

        mock_task_service.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_provided_mandatory_fields_pass_validation(self, mock_project, mock_task_service):
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
        )

        result = await tool.function(
            title="New Task",
            codebase_name="backend",
            custom_fields={"priority": "high"},
        )

        result_data = json.loads(result)
        assert result_data["task_id"] == 42
        mock_task_service.create_task.assert_called_once()
