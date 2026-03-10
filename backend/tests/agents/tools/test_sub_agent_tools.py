"""Tests for sub-agent tools, including the codebase investigation tool."""

import datetime
import inspect
import json
from typing import Literal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.config_types import AgentEngineModelConfig
from devboard.agents.engines import AgentEngine
from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.roles import AgentRoleType
from devboard.agents.tools.sub_agent_tools import (
    CodebaseInvestigationContext,
    SubAgentResult,
    _active_investigation_sessions,
    _active_sub_agent_sessions,
    create_code_review_tool,
    create_multi_codebase_investigation_tool,
    create_task_codebase_investigation_tool,
    run_sub_agent,
)
from devboard.db.models.codebase import Codebase
from devboard.db.models.project import Project
from devboard.db.models.task import Task
from devboard.integrations.types import FileDiff, StructuredDiff
from devboard.services.task_git.diff_service import TaskDiffService


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

    @pytest.mark.asyncio
    async def test_concurrent_same_session_id_raises_model_retry(self, mock_codebases, mock_agent_config_service):
        """Test that concurrent calls with the same session_id raise ModelRetry."""
        tool = create_multi_codebase_investigation_tool(mock_codebases, mock_agent_config_service)

        _active_investigation_sessions.add("session-abc")
        try:
            with pytest.raises(ModelRetry, match="session-abc.*already in use"):
                await tool.function(codebase_name="backend", query="How does X work?", session_id="session-abc")
        finally:
            _active_investigation_sessions.discard("session-abc")

    @pytest.mark.asyncio
    async def test_session_id_released_after_successful_execution(self, mock_codebases, mock_agent_config_service):
        """Test that session_id is released from active set after successful execution."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent_instance = AsyncMock()
        mock_agent_instance.session_id = "session-xyz"
        final_message = TextMessage(
            role=MessageRole.AGENT, text_content="Investigation result", timestamp=datetime.datetime.now()
        )
        mock_agent_instance.run.return_value = [final_message]

        tool = create_multi_codebase_investigation_tool(mock_codebases, mock_agent_config_service)

        with patch(
            "devboard.agents.engines.claude_code.agent.ClaudeCodeAgent",
            return_value=mock_agent_instance,
        ):
            await tool.function(codebase_name="backend", query="How does X work?", session_id="session-xyz")

        assert "session-xyz" not in _active_investigation_sessions

    @pytest.mark.asyncio
    async def test_session_id_released_after_failed_execution(self, mock_codebases, mock_agent_config_service):
        """Test that session_id is released from active set even when execution fails."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.side_effect = RuntimeError("Agent failed")

        tool = create_multi_codebase_investigation_tool(mock_codebases, mock_agent_config_service)

        with patch(
            "devboard.agents.engines.claude_code.agent.ClaudeCodeAgent",
            return_value=mock_agent_instance,
        ):
            with pytest.raises(RuntimeError, match="Agent failed"):
                await tool.function(codebase_name="backend", query="How does X work?", session_id="session-fail")

        assert "session-fail" not in _active_investigation_sessions

    @pytest.mark.asyncio
    async def test_none_session_id_does_not_interact_with_active_sessions(
        self, mock_codebases, mock_agent_config_service
    ):
        """Test that session_id=None does not add to or interact with _active_investigation_sessions."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent_instance = AsyncMock()
        mock_agent_instance.session_id = None
        final_message = TextMessage(role=MessageRole.AGENT, text_content="Result", timestamp=datetime.datetime.now())
        mock_agent_instance.run.return_value = [final_message]

        tool = create_multi_codebase_investigation_tool(mock_codebases, mock_agent_config_service)

        sessions_before = set(_active_investigation_sessions)
        with patch(
            "devboard.agents.engines.claude_code.agent.ClaudeCodeAgent",
            return_value=mock_agent_instance,
        ):
            await tool.function(codebase_name="backend", query="How does X work?", session_id=None)

        assert _active_investigation_sessions == sessions_before

    @pytest.mark.asyncio
    async def test_different_session_ids_allowed_concurrently(self, mock_codebases, mock_agent_config_service):
        """Test that different session_ids can run concurrently without conflict."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent_instance = AsyncMock()
        mock_agent_instance.session_id = "session-2"
        final_message = TextMessage(role=MessageRole.AGENT, text_content="Result", timestamp=datetime.datetime.now())
        mock_agent_instance.run.return_value = [final_message]

        tool = create_multi_codebase_investigation_tool(mock_codebases, mock_agent_config_service)

        _active_investigation_sessions.add("session-1")
        try:
            with patch(
                "devboard.agents.engines.claude_code.agent.ClaudeCodeAgent",
                return_value=mock_agent_instance,
            ):
                # Should not raise ModelRetry since session-2 is different from session-1
                await tool.function(codebase_name="backend", query="How does X work?", session_id="session-2")
        finally:
            _active_investigation_sessions.discard("session-1")


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


class TestRunSubAgent:
    """Tests for the run_sub_agent helper function."""

    @pytest.fixture
    def mock_role(self):
        """Create a mock AgentRole."""
        from devboard.agents.roles.base import AgentRole

        return Mock(spec=AgentRole)

    @pytest.mark.asyncio
    async def test_internal_engine_returns_result_with_null_session_id(self, mock_role, mock_agent_config_service):
        """Test INTERNAL engine returns SubAgentResult with session_id=None."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model = Mock()
        mock_config.model_id = "test-model"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent = AsyncMock()
        final_message = TextMessage(
            role=MessageRole.AGENT, text_content="Review result", timestamp=datetime.datetime.now()
        )
        mock_agent.run.return_value = [final_message]

        with patch("devboard.agents.engines.internal.agent.InternalAgent", return_value=mock_agent):
            result = await run_sub_agent(
                role=mock_role,
                role_type=AgentRoleType.CODE_REVIEW,
                prompt="Review this",
                agent_config_service=mock_agent_config_service,
                working_dir="/some/dir",
            )

        assert result == SubAgentResult(result="Review result", session_id=None)

    @pytest.mark.asyncio
    async def test_claude_code_engine_returns_result_with_session_id(self, mock_role, mock_agent_config_service):
        """Test CLAUDE_CODE engine returns SubAgentResult with populated session_id."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent = AsyncMock()
        mock_agent.session_id = "review-session-abc"
        final_message = TextMessage(
            role=MessageRole.AGENT, text_content="Review result", timestamp=datetime.datetime.now()
        )
        mock_agent.run.return_value = [final_message]

        with patch("devboard.agents.engines.claude_code.agent.ClaudeCodeAgent", return_value=mock_agent):
            result = await run_sub_agent(
                role=mock_role,
                role_type=AgentRoleType.CODE_REVIEW,
                prompt="Review this",
                agent_config_service=mock_agent_config_service,
                working_dir="/some/dir",
            )

        assert result == SubAgentResult(result="Review result", session_id="review-session-abc")

    @pytest.mark.asyncio
    async def test_unsupported_engine_raises_value_error(self, mock_role, mock_agent_config_service):
        """Test unsupported engine raises ValueError."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = "unsupported_engine"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        with pytest.raises(ValueError, match="Unsupported engine"):
            await run_sub_agent(
                role=mock_role,
                role_type=AgentRoleType.CODE_REVIEW,
                prompt="Review this",
                agent_config_service=mock_agent_config_service,
                working_dir="/some/dir",
            )

    @pytest.mark.asyncio
    async def test_session_guard_raises_model_retry_for_concurrent_same_session(
        self, mock_role, mock_agent_config_service
    ):
        """Test that concurrent calls with the same session_id raise ModelRetry."""
        _active_sub_agent_sessions.add("concurrent-session")
        try:
            with pytest.raises(ModelRetry, match="concurrent-session.*already in use"):
                await run_sub_agent(
                    role=mock_role,
                    role_type=AgentRoleType.CODE_REVIEW,
                    prompt="Review this",
                    agent_config_service=mock_agent_config_service,
                    working_dir="/some/dir",
                    session_id="concurrent-session",
                )
        finally:
            _active_sub_agent_sessions.discard("concurrent-session")

    @pytest.mark.asyncio
    async def test_session_id_released_after_success(self, mock_role, mock_agent_config_service):
        """Test session_id is removed from active set after successful execution."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent = AsyncMock()
        mock_agent.session_id = "cleanup-session"
        final_message = TextMessage(role=MessageRole.AGENT, text_content="Done", timestamp=datetime.datetime.now())
        mock_agent.run.return_value = [final_message]

        with patch("devboard.agents.engines.claude_code.agent.ClaudeCodeAgent", return_value=mock_agent):
            await run_sub_agent(
                role=mock_role,
                role_type=AgentRoleType.CODE_REVIEW,
                prompt="Review this",
                agent_config_service=mock_agent_config_service,
                working_dir="/some/dir",
                session_id="cleanup-session",
            )

        assert "cleanup-session" not in _active_sub_agent_sessions

    @pytest.mark.asyncio
    async def test_session_id_released_after_failure(self, mock_role, mock_agent_config_service):
        """Test session_id is removed from active set even when execution fails."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent = AsyncMock()
        mock_agent.run.side_effect = RuntimeError("Agent failed")

        with patch("devboard.agents.engines.claude_code.agent.ClaudeCodeAgent", return_value=mock_agent):
            with pytest.raises(RuntimeError, match="Agent failed"):
                await run_sub_agent(
                    role=mock_role,
                    role_type=AgentRoleType.CODE_REVIEW,
                    prompt="Review this",
                    agent_config_service=mock_agent_config_service,
                    working_dir="/some/dir",
                    session_id="fail-session",
                )

        assert "fail-session" not in _active_sub_agent_sessions

    @pytest.mark.asyncio
    async def test_none_session_id_does_not_interact_with_active_sessions(self, mock_role, mock_agent_config_service):
        """Test session_id=None does not add to or interact with _active_sub_agent_sessions."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.CLAUDE_CODE
        mock_config.model = Mock()
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_agent = AsyncMock()
        mock_agent.session_id = None
        final_message = TextMessage(role=MessageRole.AGENT, text_content="Done", timestamp=datetime.datetime.now())
        mock_agent.run.return_value = [final_message]

        sessions_before = set(_active_sub_agent_sessions)

        with patch("devboard.agents.engines.claude_code.agent.ClaudeCodeAgent", return_value=mock_agent):
            await run_sub_agent(
                role=mock_role,
                role_type=AgentRoleType.CODE_REVIEW,
                prompt="Review this",
                agent_config_service=mock_agent_config_service,
                working_dir="/some/dir",
                session_id=None,
            )

        assert _active_sub_agent_sessions == sessions_before


class TestCreateCodeReviewTool:
    """Tests for create_code_review_tool."""

    @pytest.fixture
    def mock_task(self):
        """Create a mock Task with specification and implementation plan."""
        codebase = Mock(spec=Codebase)
        codebase.name = "backend"
        codebase.local_path = "/path/to/backend"

        specification = Mock()
        specification.content = "Task spec content"

        implementation_plan = Mock()
        implementation_plan.content = "Implementation plan content"

        task = Mock(spec=Task)
        task.codebase = codebase
        task.specification = specification
        task.implementation_plan = implementation_plan
        task.get_current_workspace_dir.return_value = "/worktree/task-1"

        return task

    @pytest.fixture
    def mock_task_diff_service(self):
        return Mock(spec=TaskDiffService)

    def test_tool_creation_returns_correct_name(self, mock_task, mock_agent_config_service, mock_task_diff_service):
        """Test tool is created with name 'review_code_changes'."""
        tool = create_code_review_tool(mock_task, mock_agent_config_service, mock_task_diff_service)

        assert isinstance(tool, Tool)
        assert tool.name == "review_code_changes"

    @pytest.mark.asyncio
    async def test_empty_diff_returns_early_without_running_subagent(
        self, mock_task, mock_agent_config_service, mock_task_diff_service
    ):
        """Test that empty diff returns early message without invoking subagent."""
        mock_task_diff_service.get_task_all_changes = AsyncMock(
            return_value=StructuredDiff(files=[], additions=0, deletions=0)
        )

        tool = create_code_review_tool(mock_task, mock_agent_config_service, mock_task_diff_service)

        with patch("devboard.agents.tools.sub_agent_tools.run_sub_agent") as mock_run:
            result = await tool.function()

        mock_run.assert_not_called()
        parsed = json.loads(result)
        assert "No changes to review" in parsed["result"]
        assert parsed["session_id"] is None

    @pytest.mark.asyncio
    async def test_review_calls_run_sub_agent_with_code_review_role_type(
        self, mock_task, mock_agent_config_service, mock_task_diff_service
    ):
        """Test that run_sub_agent is called with CODE_REVIEW role type."""
        file_diff = FileDiff(
            file_path="src/foo.py",
            diff_content="@@ -1,1 +1,2 @@\n+new line\n",
            additions=1,
            deletions=0,
        )
        mock_task_diff_service.get_task_all_changes = AsyncMock(
            return_value=StructuredDiff(files=[file_diff], additions=1, deletions=0)
        )

        tool = create_code_review_tool(mock_task, mock_agent_config_service, mock_task_diff_service)

        with patch(
            "devboard.agents.tools.sub_agent_tools.run_sub_agent",
            return_value=SubAgentResult(result="Review complete", session_id=None),
        ) as mock_run:
            result = await tool.function()

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["role_type"] == AgentRoleType.CODE_REVIEW
        assert call_kwargs["agent_config_service"] is mock_agent_config_service
        assert call_kwargs["working_dir"] == "/worktree/task-1"

        parsed = json.loads(result)
        assert parsed == {"result": "Review complete", "session_id": None}

    @pytest.mark.asyncio
    async def test_prompt_includes_spec_plan_and_diff(
        self, mock_task, mock_agent_config_service, mock_task_diff_service
    ):
        """Test that the prompt contains spec, implementation plan, and diff content."""
        file_diff = FileDiff(
            file_path="src/bar.py",
            diff_content="@@ -0,0 +1,1 @@\n+added",
            additions=1,
            deletions=0,
        )
        mock_task_diff_service.get_task_all_changes = AsyncMock(
            return_value=StructuredDiff(files=[file_diff], additions=1, deletions=0)
        )

        tool = create_code_review_tool(mock_task, mock_agent_config_service, mock_task_diff_service)

        with patch(
            "devboard.agents.tools.sub_agent_tools.run_sub_agent",
            return_value=SubAgentResult(result="OK", session_id=None),
        ) as mock_run:
            await tool.function()

        call_kwargs = mock_run.call_args[1]
        prompt = call_kwargs["prompt"]

        assert "Task spec content" in prompt
        assert "Implementation plan content" in prompt
        assert "src/bar.py" in prompt
        assert "@@ -0,0 +1,1 @@" in prompt
