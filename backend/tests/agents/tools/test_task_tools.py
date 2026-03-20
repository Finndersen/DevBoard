"""Tests for create_task tool auto_plan functionality."""

import json
from unittest.mock import Mock, patch

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.task_tools import create_create_task_tool
from devboard.db.models import Codebase, Conversation, Project, Task, TaskStatus
from devboard.db.repositories.conversation import ConversationRepository
from devboard.services.task_service import TaskService
from devboard.workflow_actions.task_workflows import CreateImplementationPlanAction


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
    service.create_task.return_value = mock_task
    return service


@pytest.fixture
def mock_conversation_repo():
    repo = Mock(spec=ConversationRepository)
    conversation = Mock(spec=Conversation)
    conversation.id = 99
    repo.get_active_conversation_for_entity.return_value = conversation
    return repo


class TestCreateTaskAutoplan:
    """Tests for create_task tool auto_plan parameter."""

    @pytest.mark.asyncio
    async def test_auto_plan_without_specification_raises_model_retry(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """auto_plan=True without specification_content raises ModelRetry before creating task."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
        )

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(
                title="New Task",
                codebase_name="backend",
                auto_plan=True,
            )

        assert "auto_plan requires specification_content" in str(exc_info.value)
        mock_task_service.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_plan_without_conversation_repo_raises_model_retry(self, mock_project, mock_task_service):
        """auto_plan=True without conversation_repo raises ModelRetry before creating task."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=None,
        )

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(
                title="New Task",
                codebase_name="backend",
                specification_content="Some spec",
                auto_plan=True,
            )

        assert "auto_plan is not supported in this context" in str(exc_info.value)
        mock_task_service.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_plan_starts_execution_and_returns_conversation_id(
        self, mock_project, mock_task_service, mock_conversation_repo, mock_task
    ):
        """auto_plan=True with valid spec starts execution and returns active_conversation_id."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
        )

        with (
            patch(
                "devboard.workflow_actions.task_workflows.CreateImplementationPlanAction.is_available",
                return_value=True,
            ),
            patch("devboard.agents.tools.task_tools.get_execution_manager") as mock_get_mgr,
        ):
            mock_exec_manager = Mock()
            mock_get_mgr.return_value = mock_exec_manager
            result = await tool.function(
                title="New Task",
                codebase_name="backend",
                specification_content="Detailed spec content",
                auto_plan=True,
            )

        result_data = json.loads(result)
        assert result_data["task_id"] == mock_task.id
        assert result_data["active_conversation_id"] == 99
        mock_exec_manager.start_agent_execution.assert_called_once_with(
            99,
            CreateImplementationPlanAction.PROMPT,
        )

    @pytest.mark.asyncio
    async def test_auto_plan_false_does_not_start_execution(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """auto_plan=False (default) does not start any execution."""
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
    async def test_auto_plan_raises_when_task_not_eligible(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """auto_plan=True raises ModelRetry when CreateImplementationPlanAction.is_available returns False."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            conversation_repo=mock_conversation_repo,
        )

        with (
            patch(
                "devboard.workflow_actions.task_workflows.CreateImplementationPlanAction.is_available",
                return_value=False,
            ),
            pytest.raises(ModelRetry) as exc_info,
        ):
            await tool.function(
                title="New Task",
                codebase_name="backend",
                specification_content="Some spec",
                auto_plan=True,
            )

        assert "Cannot auto-plan" in str(exc_info.value)

    def test_auto_plan_field_in_json_schema(self, mock_project, mock_task_service):
        """auto_plan field appears in the JSON schema with correct type and default."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
        )
        schema = tool.tool_def.parameters_json_schema
        props = schema["properties"]

        assert "auto_plan" in props
        auto_plan_schema = props["auto_plan"]
        assert auto_plan_schema["type"] == "boolean"
        assert auto_plan_schema["default"] is False
        assert "specification_content" in auto_plan_schema["description"]
