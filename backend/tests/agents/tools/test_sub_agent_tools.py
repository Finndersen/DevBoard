"""Tests for sub-agent tools, including the codebase investigation tool."""

import datetime
import inspect
import json
from typing import Literal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.config_types import AgentEngineModelConfig
from devboard.agents.engines import AgentEngine
from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.tools.sub_agent_tools import (
    CodebaseInvestigationContext,
    create_multi_codebase_investigation_tool,
    create_task_codebase_investigation_tool,
)
from devboard.db.models.codebase import Codebase
from devboard.db.models.project import Project
from devboard.db.models.task import Task


@pytest.fixture
def mock_codebases():
    """Create mock CodebaseInvestigationContext instances."""
    backend_codebase = Mock(spec=Codebase)
    backend_codebase.id = 1
    backend_codebase.name = "backend"
    backend_codebase.description = "Backend codebase"
    backend_codebase.local_path = "/path/to/backend"

    frontend_codebase = Mock(spec=Codebase)
    frontend_codebase.id = 2
    frontend_codebase.name = "frontend"
    frontend_codebase.description = "Frontend codebase"
    frontend_codebase.local_path = "/path/to/frontend"

    backend_context = CodebaseInvestigationContext(
        codebase=backend_codebase,
        working_dir="/path/to/backend",
    )

    frontend_context = CodebaseInvestigationContext(
        codebase=frontend_codebase,
        working_dir="/path/to/frontend",
    )

    return [backend_context, frontend_context]


@pytest.fixture
def mock_agent_config_service():
    """Create a mock AgentConfigService."""
    return Mock(spec=AgentConfigService)


class TestCreateCodebaseInvestigationTool:
    """Tests for create_codebase_investigation_tool."""

    def test_tool_creation_with_single_codebase(self, mock_codebases, mock_agent_config_service):
        """Test tool is created correctly with a single codebase."""
        tool = create_multi_codebase_investigation_tool(
            [mock_codebases[0]],
            mock_agent_config_service,
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"
        assert tool.function is not None

    def test_tool_creation_with_multiple_codebases(self, mock_codebases, mock_agent_config_service):
        """Test tool is created correctly with multiple codebases."""
        tool = create_multi_codebase_investigation_tool(
            mock_codebases,
            mock_agent_config_service,
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"
        assert tool.function is not None

    def test_raises_error_with_empty_list(self, mock_agent_config_service):
        """Test that empty codebase list raises ValueError."""
        with pytest.raises(ValueError, match="At least one codebase must be provided"):
            create_multi_codebase_investigation_tool([], mock_agent_config_service)

    def test_dynamic_literal_annotation_single_codebase(self, mock_codebases, mock_agent_config_service):
        """Test that Literal annotation is set correctly for single codebase."""
        tool = create_multi_codebase_investigation_tool(
            [mock_codebases[0]],
            mock_agent_config_service,
        )

        # Check that the annotation was dynamically set
        annotations = tool.function.__annotations__
        assert "codebase_name" in annotations

        # The annotation should be a Literal type with the codebase name
        codebase_name_type = annotations["codebase_name"]
        assert hasattr(codebase_name_type, "__origin__")
        assert codebase_name_type.__origin__ is Literal

        # Check the literal values
        assert codebase_name_type.__args__ == ("backend",)

    def test_dynamic_literal_annotation_multiple_codebases(self, mock_codebases, mock_agent_config_service):
        """Test that Literal annotation is set correctly for multiple codebases."""
        tool = create_multi_codebase_investigation_tool(
            mock_codebases,
            mock_agent_config_service,
        )

        # Check that the annotation was dynamically set
        annotations = tool.function.__annotations__
        assert "codebase_name" in annotations

        # The annotation should be a Literal type with all codebase names
        codebase_name_type = annotations["codebase_name"]
        assert hasattr(codebase_name_type, "__origin__")
        assert codebase_name_type.__origin__ is Literal

        # Check the literal values
        assert set(codebase_name_type.__args__) == {"backend", "frontend"}

    def test_function_signature_has_codebase_name_parameter(self, mock_codebases, mock_agent_config_service):
        """Test that the tool function has expected parameters."""
        tool = create_multi_codebase_investigation_tool(
            mock_codebases,
            mock_agent_config_service,
        )

        sig = inspect.signature(tool.function)
        params = sig.parameters

        # Check parameters exist
        assert "query" in params
        assert "codebase_name" in params
        assert "session_id" in params

        # Check parameter annotations
        assert params["query"].annotation is str
        assert params["codebase_name"].annotation is not str  # Should be Literal type
        assert params["session_id"].annotation == str | None
        assert params["session_id"].default is None

    @pytest.mark.asyncio
    async def test_investigate_returns_json_with_result_and_session_id_claude_code(
        self, mock_codebases, mock_agent_config_service
    ):
        """Test that the tool returns JSON with result and session_id for ClaudeCode engine."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent_instance = AsyncMock()
        mock_agent_instance.session_id = "test-session-123"
        final_message = TextMessage(
            role=MessageRole.AGENT, text_content="Investigation result", timestamp=datetime.datetime.now()
        )
        mock_agent_instance.run.return_value = [final_message]

        tool = create_multi_codebase_investigation_tool(mock_codebases, mock_agent_config_service)

        with patch(
            "devboard.agents.engines.claude_code.agent.ClaudeCodeAgent",
            return_value=mock_agent_instance,
        ):
            result = await tool.function(codebase_name="backend", query="How does X work?")

        parsed = json.loads(result)
        assert parsed == {
            "result": "Investigation result",
            "session_id": "test-session-123",
        }

    @pytest.mark.asyncio
    async def test_investigate_internal_agent_returns_null_session_id(self, mock_codebases, mock_agent_config_service):
        """Test that InternalAgent engine returns null session_id."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model = Mock()
        mock_config.model_id = "test-model"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent_instance = AsyncMock()
        final_message = TextMessage(
            role=MessageRole.AGENT, text_content="Internal result", timestamp=datetime.datetime.now()
        )
        mock_agent_instance.run.return_value = [final_message]

        tool = create_multi_codebase_investigation_tool(mock_codebases, mock_agent_config_service)

        with patch(
            "devboard.agents.engines.internal.agent.InternalAgent",
            return_value=mock_agent_instance,
        ):
            result = await tool.function(codebase_name="backend", query="How does Y work?")

        parsed = json.loads(result)
        assert parsed == {
            "result": "Internal result",
            "session_id": None,
        }

    @pytest.mark.asyncio
    async def test_investigate_passes_session_id_to_claude_code_agent(self, mock_codebases, mock_agent_config_service):
        """Test that session_id is passed to ClaudeCodeAgent constructor."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent_instance = AsyncMock()
        mock_agent_instance.session_id = "resumed-session-456"
        final_message = TextMessage(
            role=MessageRole.AGENT, text_content="Follow-up result", timestamp=datetime.datetime.now()
        )
        mock_agent_instance.run.return_value = [final_message]

        tool = create_multi_codebase_investigation_tool(mock_codebases, mock_agent_config_service)

        with patch(
            "devboard.agents.engines.claude_code.agent.ClaudeCodeAgent",
            return_value=mock_agent_instance,
        ) as mock_claude_code_cls:
            await tool.function(
                codebase_name="backend",
                query="Follow-up question",
                session_id="previous-session-456",
            )

        mock_claude_code_cls.assert_called_once()
        call_kwargs = mock_claude_code_cls.call_args[1]
        assert call_kwargs["session_id"] == "previous-session-456"


class TestCreateTaskCodebaseInvestigationTool:
    """Tests for create_task_codebase_investigation_tool."""

    @pytest.fixture
    def task_with_single_project_codebase(self, mock_codebases):
        """Create a mock task with a project that has only the task's codebase."""
        task_codebase = mock_codebases[0].codebase

        project = Mock(spec=Project)
        project.codebases = [task_codebase]

        task = Mock(spec=Task)
        task.codebase = task_codebase
        task.codebase_id = task_codebase.id
        task.project = project
        task.get_current_workspace_dir.return_value = "/worktree/task-1"

        return task

    @pytest.fixture
    def task_with_multiple_project_codebases(self, mock_codebases):
        """Create a mock task with a project that has multiple codebases."""
        task_codebase = mock_codebases[0].codebase
        other_codebase = mock_codebases[1].codebase

        project = Mock(spec=Project)
        project.codebases = [task_codebase, other_codebase]

        task = Mock(spec=Task)
        task.codebase = task_codebase
        task.codebase_id = task_codebase.id
        task.project = project
        task.get_current_workspace_dir.return_value = "/worktree/task-1"

        return task

    def test_tool_creation_with_single_project_codebase(
        self, task_with_single_project_codebase, mock_agent_config_service
    ):
        """Test tool is created correctly when project has only task's codebase."""
        tool = create_task_codebase_investigation_tool(
            task_with_single_project_codebase,
            mock_agent_config_service,
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"

        # Should only have the task's codebase
        codebase_name_type = tool.function.__annotations__["codebase_name"]
        assert codebase_name_type.__args__ == ("backend",)

    def test_tool_creation_with_multiple_project_codebases(
        self, task_with_multiple_project_codebases, mock_agent_config_service
    ):
        """Test tool includes all project codebases."""
        tool = create_task_codebase_investigation_tool(
            task_with_multiple_project_codebases,
            mock_agent_config_service,
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"

        # Should have both codebases
        codebase_name_type = tool.function.__annotations__["codebase_name"]
        assert set(codebase_name_type.__args__) == {"backend", "frontend"}

    def test_task_codebase_uses_worktree_directory(
        self, task_with_multiple_project_codebases, mock_agent_config_service
    ):
        """Test that task's codebase uses worktree directory, not local_path."""
        task = task_with_multiple_project_codebases

        # Verify worktree is called during tool creation
        create_task_codebase_investigation_tool(task, mock_agent_config_service)
        task.get_current_workspace_dir.assert_called_once()
