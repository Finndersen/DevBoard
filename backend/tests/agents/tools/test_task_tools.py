"""Tests for create_task tool functionality."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.config_types import AgentEngineModelConfig
from devboard.agents.language_models import ModelType
from devboard.agents.roles import AgentRoleType
from devboard.agents.tools.task_tools import (
    create_create_task_tool,
    create_edit_task_tool,
    create_view_task_details_tool,
)
from devboard.db.models import Codebase, Conversation, ParentEntityType, Project, Task, TaskStatus
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.document import DocumentRepository
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
    repo.db = Mock()
    return repo


@pytest.fixture
def mock_agent_config_service():
    service = Mock(spec=AgentConfigService)
    # Mock config with model and model_type
    mock_model = Mock()
    mock_model.model_type = ModelType.ADVANCED
    mock_config = Mock(spec=AgentEngineModelConfig)
    mock_config.model = mock_model
    mock_config.engine = "anthropic"
    service.get_effective_config.return_value = mock_config
    service.get_model_id_for_type.return_value = "anthropic:claude-opus-4"
    return service


class TestCreateTaskInitialPrompt:
    """Tests for create_task tool initial_prompt parameter."""

    @pytest.mark.asyncio
    async def test_initial_prompt_without_conversation_repo_raises_model_retry(
        self, mock_project, mock_task_service, mock_agent_config_service
    ):
        """initial_prompt without conversation_repo raises ModelRetry before creating task."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
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
        self, mock_project, mock_task_service, mock_conversation_repo, mock_task, mock_agent_config_service
    ):
        """initial_prompt starts execution with the provided prompt string."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
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
        self, mock_project, mock_task_service, mock_conversation_repo, mock_task, mock_agent_config_service
    ):
        """initial_prompt causes active_conversation_id to be included in response."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
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
        self, mock_project, mock_task_service, mock_conversation_repo, mock_agent_config_service
    ):
        """initial_prompt=None (default) does not start any execution."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
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
        self, mock_project, mock_task_service, mock_conversation_repo, mock_agent_config_service
    ):
        """initial_prompt does not require specification_content."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
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
        self, mock_project, mock_task_service, mock_conversation_repo, mock_agent_config_service
    ):
        """initial_prompt and specification_content can be provided together."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
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

    def test_initial_prompt_field_in_json_schema(self, mock_project, mock_task_service, mock_agent_config_service):
        """initial_prompt field appears in the JSON schema with correct type and default."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
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
    async def test_creates_task_and_returns_task_id(
        self, mock_project, mock_task_service, mock_task, mock_agent_config_service
    ):
        """Branch creation is now handled inside TaskService.create_task."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
        )

        result = await tool.function(title="New Task", codebase_name="backend")

        mock_task_service.create_task.assert_called_once()
        result_data = json.loads(result)
        assert result_data["task_id"] == mock_task.id

    @pytest.mark.asyncio
    async def test_task_service_failure_raises_model_retry(
        self, mock_project, mock_task_service, mock_agent_config_service
    ):
        """Service errors (including branch failures) wrap into ModelRetry."""
        mock_task_service.create_task.side_effect = ValueError("git error")

        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
        )

        with pytest.raises(ModelRetry, match="Failed to create task"):
            await tool.function(title="New Task", codebase_name="backend")


class TestCreateTaskMandatoryCustomFields:
    """Tests for mandatory custom field validation in create_task tool.

    Validation is now performed inside TaskService.create_task, so errors surface
    as ModelRetry wrapping the ValueError raised by the service.
    """

    @pytest.mark.asyncio
    async def test_missing_mandatory_fields_raises_model_retry(
        self, mock_project, mock_task_service, mock_agent_config_service
    ):
        mock_task_service.create_task.side_effect = ValueError("Missing required custom fields: priority")

        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
        )

        with pytest.raises(ModelRetry, match="Missing required custom fields: priority"):
            await tool.function(title="New Task", codebase_name="backend")

        mock_task_service.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_provided_mandatory_fields_pass_validation(
        self, mock_project, mock_task_service, mock_agent_config_service
    ):
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
        )

        result = await tool.function(
            title="New Task",
            codebase_name="backend",
            custom_fields={"priority": "high"},
        )

        result_data = json.loads(result)
        assert result_data["task_id"] == 42
        mock_task_service.create_task.assert_called_once()


class TestViewTaskDetailsTool:
    """Tests for view_task_details tool with conversation support."""

    @pytest.fixture
    def mock_codebase_for_view(self):
        codebase = Mock(spec=Codebase)
        codebase.id = 10
        codebase.name = "backend"
        return codebase

    @pytest.fixture
    def mock_task_for_view(self, mock_codebase_for_view):
        task = Mock(spec=Task)
        task.id = 42
        task.project_id = 1
        task.title = "Test Task"
        task.status = TaskStatus.PLANNING
        task.branch_name = "test-task"
        task.base_branch = "main"
        task.github_pr_number = None
        task.custom_fields = None
        task.created_at = datetime(2024, 1, 1, 12, 0, 0)
        task.codebase = mock_codebase_for_view
        task.specification = None
        task.implementation_plan = None
        task.change_summary = None
        return task

    @pytest.fixture
    def mock_task_service_for_view(self, mock_task_for_view):
        service = Mock(spec=TaskService)
        service.get_task_by_id.return_value = mock_task_for_view
        service.is_task_agent_running.return_value = False
        return service

    @pytest.mark.asyncio
    async def test_view_task_details_without_conversations(self, mock_task_service_for_view):
        """view_task_details returns task info when conversation_repo is not provided."""
        tool = create_view_task_details_tool(None, mock_task_service_for_view)
        result = await tool.function(task_id=42, include_documents=None)

        assert "# Task #42: Test Task" in result
        assert "**Status:** planning" in result
        assert "**Branch:** test-task" in result
        assert "## Conversations" not in result

    @pytest.mark.asyncio
    async def test_view_task_details_with_no_conversations(self, mock_task_service_for_view):
        """view_task_details does not show Conversations section when no conversations exist."""
        conversation_repo = Mock(spec=ConversationRepository)
        conversation_repo.get_active_conversations_for_entity.return_value = []

        tool = create_view_task_details_tool(None, mock_task_service_for_view, conversation_repo)
        result = await tool.function(task_id=42, include_documents=None)

        assert "# Task #42: Test Task" in result
        assert "## Conversations" not in result
        conversation_repo.get_active_conversations_for_entity.assert_called_once_with(ParentEntityType.TASK, 42)

    @pytest.mark.asyncio
    async def test_view_task_details_with_conversations(self, mock_task_service_for_view):
        """view_task_details shows Conversations section when conversations exist."""
        conversation = Mock(spec=Conversation)
        conversation.id = 99
        conversation.agent_role = AgentRoleType.TASK_PLANNING
        conversation.last_activity_at = datetime(2024, 1, 1, 13, 30, 0)

        conversation_repo = Mock(spec=ConversationRepository)
        conversation_repo.get_active_conversations_for_entity.return_value = [conversation]

        with patch("devboard.agents.tools.task_tools.get_execution_manager") as mock_get_mgr:
            mock_exec_manager = Mock()
            mock_exec_manager.has_active_execution.return_value = False
            mock_get_mgr.return_value = mock_exec_manager

            tool = create_view_task_details_tool(None, mock_task_service_for_view, conversation_repo)
            result = await tool.function(task_id=42, include_documents=None)

            assert "# Task #42: Test Task" in result
            assert "## Conversations" in result
            assert "[99]" in result
            assert "task_planning" in result
            assert "inactive" in result
            assert "2024-01-01T13:30:00" in result

    @pytest.mark.asyncio
    async def test_view_task_details_with_running_conversation(self, mock_task_service_for_view):
        """view_task_details shows 'running' status for active executions."""
        conversation = Mock(spec=Conversation)
        conversation.id = 99
        conversation.agent_role = AgentRoleType.TASK_PLANNING
        conversation.last_activity_at = datetime(2024, 1, 1, 13, 30, 0)

        conversation_repo = Mock(spec=ConversationRepository)
        conversation_repo.get_active_conversations_for_entity.return_value = [conversation]

        with patch("devboard.agents.tools.task_tools.get_execution_manager") as mock_get_mgr:
            mock_exec_manager = Mock()
            mock_exec_manager.has_active_execution.return_value = True
            mock_get_mgr.return_value = mock_exec_manager

            tool = create_view_task_details_tool(None, mock_task_service_for_view, conversation_repo)
            result = await tool.function(task_id=42, include_documents=None)

            assert "running" in result
            assert "inactive" not in result

    @pytest.mark.asyncio
    async def test_view_task_details_with_multiple_conversations(self, mock_task_service_for_view):
        """view_task_details shows all conversations ordered by last_activity_at."""
        conv1 = Mock(spec=Conversation)
        conv1.id = 99
        conv1.agent_role = AgentRoleType.TASK_PLANNING
        conv1.last_activity_at = datetime(2024, 1, 1, 13, 30, 0)

        conv2 = Mock(spec=Conversation)
        conv2.id = 100
        conv2.agent_role = AgentRoleType.TASK_IMPLEMENTATION
        conv2.last_activity_at = datetime(2024, 1, 1, 14, 0, 0)

        conversation_repo = Mock(spec=ConversationRepository)
        conversation_repo.get_active_conversations_for_entity.return_value = [conv2, conv1]

        with patch("devboard.agents.tools.task_tools.get_execution_manager") as mock_get_mgr:
            mock_exec_manager = Mock()
            mock_exec_manager.has_active_execution.return_value = False
            mock_get_mgr.return_value = mock_exec_manager

            tool = create_view_task_details_tool(None, mock_task_service_for_view, conversation_repo)
            result = await tool.function(task_id=42, include_documents=None)

            assert "[100]" in result
            assert "[99]" in result
            assert "task_implementation" in result
            assert "task_planning" in result


class TestCreateTaskModelType:
    """Tests for create_task model_type parameter."""

    @pytest.mark.asyncio
    async def test_model_type_defaults_from_config(self, mock_project, mock_task_service, mock_agent_config_service):
        """model_type defaults to the value from agent config."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
        )

        # Verify default is set from config (mock returns ModelType.ADVANCED)
        schema = tool.tool_def.parameters_json_schema
        props = schema["properties"]
        assert props["model_type"]["default"] == "advanced"

    @pytest.mark.asyncio
    async def test_model_type_resolves_to_model_id(
        self, mock_project, mock_task_service, mock_agent_config_service, mock_task
    ):
        """model_type is resolved to model_id and passed to task_service."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
        )

        await tool.function(
            title="New Task",
            codebase_name="backend",
            model_type="standard",
        )

        # Verify that get_model_id_for_type was called with the correct arguments
        mock_agent_config_service.get_model_id_for_type.assert_called_once()
        call_args = mock_agent_config_service.get_model_id_for_type.call_args
        assert call_args[0][0] == ModelType.STANDARD  # model_type enum
        assert call_args[0][1] == "anthropic"  # engine from config

        # Verify that task_service.create_task was called with model_id_override
        mock_task_service.create_task.assert_called_once()
        call_kwargs = mock_task_service.create_task.call_args.kwargs
        assert call_kwargs["model_id_override"] == "anthropic:claude-opus-4"

    @pytest.mark.asyncio
    async def test_invalid_model_type_raises_model_retry(
        self, mock_project, mock_task_service, mock_agent_config_service
    ):
        """Invalid model_type value raises ModelRetry."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
        )

        with pytest.raises(ModelRetry, match="Invalid model_type"):
            await tool.function(
                title="New Task",
                codebase_name="backend",
                model_type="invalid",
            )

    def test_model_type_field_in_json_schema(self, mock_project, mock_task_service, mock_agent_config_service):
        """model_type field appears in JSON schema with correct enum values."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
        )
        schema = tool.tool_def.parameters_json_schema
        props = schema["properties"]

        assert "model_type" in props
        model_type_schema = props["model_type"]
        assert model_type_schema["enum"] == ["fast", "standard", "advanced"]
        assert model_type_schema["default"] == "advanced"


class TestTaskToolSpecGuidance:
    """Tests for specification guidance in task tool schemas."""

    def test_create_task_specification_content_includes_guidance(
        self, mock_project, mock_task_service, mock_agent_config_service
    ):
        """create_task specification_content description includes required guidance."""
        tool = create_create_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            agent_config_service=mock_agent_config_service,
        )
        schema = tool.tool_def.parameters_json_schema
        spec_description = schema["properties"]["specification_content"]["description"]

        # Verify key guidance points are present
        assert "goal (what and why)" in spec_description
        assert "relevant background" in spec_description
        assert "functional requirements and constraints" in spec_description
        assert "critical implementation details" in spec_description
        assert "Should NOT include routine implementation steps" in spec_description
        assert "bullet points" in spec_description
        assert "tables" in spec_description
        assert "diagrams" in spec_description

    def test_edit_task_specification_content_includes_guidance(self, mock_project, mock_task_service):
        """edit_task specification_content description includes required guidance."""
        document_repo = Mock(spec=DocumentRepository)
        tool = create_edit_task_tool(
            project=mock_project,
            task_service=mock_task_service,
            document_repository=document_repo,
        )
        schema = tool.tool_def.parameters_json_schema
        spec_description = schema["properties"]["specification_content"]["description"]

        # Verify key guidance points are present
        assert "goal (what and why)" in spec_description
        assert "relevant background" in spec_description
        assert "functional requirements and constraints" in spec_description
        assert "critical implementation details" in spec_description
        assert "Should NOT include routine implementation steps" in spec_description
        assert "bullet points" in spec_description
        assert "tables" in spec_description
        assert "diagrams" in spec_description
        # Edit tool should also mention "leave null to keep unchanged"
        assert "Leave null to keep unchanged" in spec_description
