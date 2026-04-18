"""Tests for sub-agent tools, including the codebase investigation tool."""

import asyncio
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
from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution.manager import ConversationExecutionManager
from devboard.agents.execution.types import ExecutionStatus, SubAgentResult
from devboard.agents.language_models import ModelType
from devboard.agents.roles import AgentRoleType
from devboard.agents.tools.sub_agent_tools import (
    _MAX_FILE_DIFF_CHARS,
    _MAX_TOTAL_DIFF_CHARS,
    CodebaseInvestigationContext,
    build_code_review_prompt,
    create_multi_codebase_investigation_tool,
    create_sub_agent_conversation,
    create_task_codebase_investigation_tool,
    run_sub_agent,
)
from devboard.db.models.codebase import Codebase
from devboard.db.models.enums import EntityType
from devboard.db.models.project import Project
from devboard.db.models.task import Task
from devboard.db.repositories import ConversationRepository
from devboard.integrations.types import FileDiff, StructuredDiff


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


@pytest.fixture
def mock_conversation_repo():
    """Create a mock ConversationRepository."""
    repo = Mock(spec=ConversationRepository)
    mock_conversation = Mock()
    mock_conversation.id = 42
    mock_conversation.parent_conversation_id = None
    repo.create.return_value = mock_conversation
    repo.get_by_id.return_value = mock_conversation
    return repo


@pytest.fixture
def mock_execution_manager():
    """Create a mock ConversationExecutionManager."""
    return Mock(spec=ConversationExecutionManager)


def make_mock_task(task_id: int = 1) -> Mock:
    """Create a mock Task with entity_type and id."""
    mock_task = Mock(spec=Task)
    mock_task.id = task_id
    mock_task.entity_type = EntityType.TASK
    return mock_task


def make_investigation_tool(
    codebases, agent_config_service, conversation_repo, execution_manager, parent_conversation_id=None
):
    """Helper to create investigation tool with required params."""
    return create_multi_codebase_investigation_tool(
        codebases,
        agent_config_service,
        conversation_repo=conversation_repo,
        parent_entity=make_mock_task(),
        parent_conversation_id=parent_conversation_id,
        execution_manager=execution_manager,
    )


class TestCreateCodebaseInvestigationTool:
    """Tests for create_codebase_investigation_tool."""

    def test_tool_creation_with_single_codebase(
        self, mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
    ):
        """Test tool is created correctly with a single codebase."""
        tool = make_investigation_tool(
            [mock_codebases[0]], mock_agent_config_service, mock_conversation_repo, mock_execution_manager
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"
        assert tool.function is not None

    def test_tool_creation_with_multiple_codebases(
        self, mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
    ):
        """Test tool is created correctly with multiple codebases."""
        tool = make_investigation_tool(
            mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"
        assert tool.function is not None

    def test_raises_error_with_empty_list(
        self, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
    ):
        """Test that empty codebase list raises ValueError."""
        with pytest.raises(ValueError, match="At least one codebase must be provided"):
            make_investigation_tool([], mock_agent_config_service, mock_conversation_repo, mock_execution_manager)

    def test_dynamic_literal_annotation_single_codebase(
        self, mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
    ):
        """Test that Literal annotation is set correctly for single codebase."""
        tool = make_investigation_tool(
            [mock_codebases[0]], mock_agent_config_service, mock_conversation_repo, mock_execution_manager
        )

        annotations = tool.function.__annotations__
        assert "codebase_name" in annotations

        codebase_name_type = annotations["codebase_name"]
        assert hasattr(codebase_name_type, "__origin__")
        assert codebase_name_type.__origin__ is Literal
        assert codebase_name_type.__args__ == ("backend",)

    def test_dynamic_literal_annotation_multiple_codebases(
        self, mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
    ):
        """Test that Literal annotation is set correctly for multiple codebases."""
        tool = make_investigation_tool(
            mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
        )

        annotations = tool.function.__annotations__
        assert "codebase_name" in annotations

        codebase_name_type = annotations["codebase_name"]
        assert hasattr(codebase_name_type, "__origin__")
        assert codebase_name_type.__origin__ is Literal
        assert set(codebase_name_type.__args__) == {"backend", "frontend"}

    def test_function_signature_has_codebase_name_parameter(
        self, mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
    ):
        """Test that the tool function has expected parameters."""
        tool = make_investigation_tool(
            mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
        )

        sig = inspect.signature(tool.function)
        params = sig.parameters

        assert "query" in params
        assert "codebase_name" in params
        assert "conversation_id" in params

        # Annotations may be strings due to from __future__ import annotations
        query_annotation = params["query"].annotation
        assert query_annotation is str or query_annotation == "str"
        assert params["codebase_name"].annotation is not str  # Should be Literal type
        conv_id_annotation = params["conversation_id"].annotation
        assert conv_id_annotation == int | None or conv_id_annotation == "int | None"
        assert params["conversation_id"].default is None

    @pytest.mark.asyncio
    async def test_investigate_creates_conversation_and_returns_json_with_conversation_id(
        self, mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
    ):
        """Test that the tool creates a conversation and returns JSON with session_id (conversation_id)."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model = Mock()
        mock_config.model_id = "test-model"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_sub_agent_result = SubAgentResult(result="Investigation result", conversation_id=42)
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        tool = make_investigation_tool(
            mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
        )

        result = await tool.function(codebase_name="backend", query="How does X work?")

        parsed = json.loads(result)
        assert parsed == {
            "result": "Investigation result",
            "conversation_id": 42,
        }
        mock_conversation_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_investigate_resumes_conversation_by_session_id(
        self, mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
    ):
        """Test that passing session_id (int) resumes an existing conversation."""
        existing_conversation = Mock()
        existing_conversation.id = 99
        existing_conversation.parent_conversation_id = None  # matches parent_conversation_id=None
        mock_conversation_repo.get_by_id.return_value = existing_conversation

        mock_sub_agent_result = SubAgentResult(result="Follow-up result", conversation_id=99)
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        tool = make_investigation_tool(
            mock_codebases,
            mock_agent_config_service,
            mock_conversation_repo,
            mock_execution_manager,
            parent_conversation_id=None,
        )

        result = await tool.function(codebase_name="backend", query="Follow-up question", conversation_id=99)

        parsed = json.loads(result)
        assert parsed["conversation_id"] == 99
        mock_conversation_repo.get_by_id.assert_called_once_with(99)
        mock_conversation_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_concurrent_same_session_id_raises_model_retry(
        self, mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
    ):
        """Test that concurrent calls with the same session_id raise ModelRetry (via ConversationBusyError)."""
        mock_conv = Mock()
        mock_conv.id = 55
        mock_conv.parent_conversation_id = None
        mock_conversation_repo.get_by_id.return_value = mock_conv

        mock_execution_manager.run_sub_agent_execution = AsyncMock(side_effect=ConversationBusyError(55))

        tool = make_investigation_tool(
            mock_codebases, mock_agent_config_service, mock_conversation_repo, mock_execution_manager
        )

        with pytest.raises(ModelRetry):
            await tool.function(codebase_name="backend", query="How does X work?", conversation_id=55)


class TestCreateTaskCodebaseInvestigationTool:
    """Tests for create_task_codebase_investigation_tool."""

    @pytest.fixture
    def mock_conv_repo(self):
        return Mock(spec=ConversationRepository)

    @pytest.fixture
    def mock_exec_manager(self):
        return Mock(spec=ConversationExecutionManager)

    @pytest.fixture
    def task_with_single_project_codebase(self, mock_codebases):
        """Create a mock task with a project that has only the task's codebase."""
        task_codebase = mock_codebases[0].codebase

        project = Mock(spec=Project)
        project.codebases = [task_codebase]

        task = Mock(spec=Task)
        task.id = 1
        task.codebase = task_codebase
        task.codebase_id = task_codebase.id
        task.project = project

        return task

    @pytest.fixture
    def task_with_multiple_project_codebases(self, mock_codebases):
        """Create a mock task with a project that has multiple codebases."""
        task_codebase = mock_codebases[0].codebase
        other_codebase = mock_codebases[1].codebase

        project = Mock(spec=Project)
        project.codebases = [task_codebase, other_codebase]

        task = Mock(spec=Task)
        task.id = 1
        task.codebase = task_codebase
        task.codebase_id = task_codebase.id
        task.project = project

        return task

    def test_tool_creation_with_single_project_codebase(
        self, task_with_single_project_codebase, mock_agent_config_service, mock_conv_repo, mock_exec_manager
    ):
        """Test tool is created correctly when project has only task's codebase."""
        tool = create_task_codebase_investigation_tool(
            task_with_single_project_codebase,
            mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_conversation_id=None,
            working_dir="/worktree/task-1",
            execution_manager=mock_exec_manager,
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"

        codebase_name_type = tool.function.__annotations__["codebase_name"]
        assert codebase_name_type.__args__ == ("backend",)

    def test_tool_creation_with_multiple_project_codebases(
        self, task_with_multiple_project_codebases, mock_agent_config_service, mock_conv_repo, mock_exec_manager
    ):
        """Test tool includes all project codebases."""
        tool = create_task_codebase_investigation_tool(
            task_with_multiple_project_codebases,
            mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_conversation_id=None,
            working_dir="/worktree/task-1",
            execution_manager=mock_exec_manager,
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"

        codebase_name_type = tool.function.__annotations__["codebase_name"]
        assert set(codebase_name_type.__args__) == {"backend", "frontend"}

    def test_task_codebase_uses_provided_working_dir(
        self, task_with_multiple_project_codebases, mock_agent_config_service, mock_conv_repo, mock_exec_manager
    ):
        """Test that tool is created using the provided working_dir (not task.get_current_workspace_dir())."""
        task = task_with_multiple_project_codebases

        tool = create_task_codebase_investigation_tool(
            task,
            mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_conversation_id=None,
            working_dir="/worktree/task-1",
            execution_manager=mock_exec_manager,
        )

        assert isinstance(tool, Tool)
        assert tool.name == "investigate_codebase"


class TestCreateSubAgentConversation:
    """Tests for the create_sub_agent_conversation helper function."""

    @pytest.fixture
    def mock_conv_repo(self):
        """Create a mock ConversationRepository."""
        repo = Mock(spec=ConversationRepository)
        mock_conversation = Mock()
        mock_conversation.id = 10
        mock_conversation.parent_conversation_id = None
        repo.create.return_value = mock_conversation
        return repo

    def test_creates_conversation_and_returns_object(self, mock_agent_config_service, mock_conv_repo):
        """Test that create_sub_agent_conversation creates conversation, commits, and returns object."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model_id = "test-model"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_entity = make_mock_task(task_id=5)

        result = create_sub_agent_conversation(
            role_type=AgentRoleType.CODE_REVIEW,
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_entity=mock_entity,
        )

        assert result.id == 10
        mock_conv_repo.create.assert_called_once()
        create_kwargs = mock_conv_repo.create.call_args[1]
        assert create_kwargs["is_active"] is False
        assert create_kwargs["parent_entity_id"] == 5
        assert create_kwargs["parent_conversation_id"] is None
        mock_conv_repo.commit.assert_called_once()

    def test_passes_parent_conversation_id(self, mock_agent_config_service, mock_conv_repo):
        """Test that parent_conversation_id is passed through to create."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model_id = "test-model"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        create_sub_agent_conversation(
            role_type=AgentRoleType.INVESTIGATION,
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_entity=make_mock_task(task_id=3),
            parent_conversation_id=99,
        )

        create_kwargs = mock_conv_repo.create.call_args[1]
        assert create_kwargs["parent_conversation_id"] == 99

    def test_commits_eagerly(self, mock_agent_config_service, mock_conv_repo):
        """Test that commit is called immediately after create."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model_id = "test-model"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        call_order = []
        mock_conv_repo.create.side_effect = lambda **kwargs: (
            call_order.append("create"),
            Mock(id=1, parent_conversation_id=None),
        )[1]
        mock_conv_repo.commit.side_effect = lambda: call_order.append("commit")

        create_sub_agent_conversation(
            role_type=AgentRoleType.CODE_REVIEW,
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_entity=make_mock_task(),
        )

        assert call_order == ["create", "commit"]

    def test_uses_role_default_model_when_no_model_type(self, mock_agent_config_service, mock_conv_repo):
        """When model_type is None, the role's default model_id is used."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model_id = "anthropic:claude-sonnet"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        create_sub_agent_conversation(
            role_type=AgentRoleType.STEP_EXECUTION,
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_entity=make_mock_task(),
            model_type=None,
        )

        create_kwargs = mock_conv_repo.create.call_args[1]
        assert create_kwargs["model_id"] == "anthropic:claude-sonnet"
        mock_agent_config_service.get_model_id_for_type.assert_not_called()

    def test_resolves_model_id_for_type_when_model_type_provided(self, mock_agent_config_service, mock_conv_repo):
        """When model_type is provided, get_model_id_for_type is called and its result used as model_id."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model_id = "anthropic:claude-sonnet"
        mock_agent_config_service.get_effective_config.return_value = mock_config
        mock_agent_config_service.get_model_id_for_type.return_value = "anthropic:claude-haiku"

        create_sub_agent_conversation(
            role_type=AgentRoleType.STEP_EXECUTION,
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_entity=make_mock_task(),
            model_type=ModelType.FAST,
        )

        mock_agent_config_service.get_model_id_for_type.assert_called_once_with(ModelType.FAST, AgentEngine.INTERNAL)
        create_kwargs = mock_conv_repo.create.call_args[1]
        assert create_kwargs["model_id"] == "anthropic:claude-haiku"


class TestRunSubAgent:
    """Tests for the run_sub_agent helper function."""

    @pytest.fixture
    def mock_role(self):
        """Create a mock AgentRole."""
        from devboard.agents.roles.base import AgentRole

        return Mock(spec=AgentRole)

    @pytest.fixture
    def mock_conv_repo(self):
        """Create a mock ConversationRepository."""
        repo = Mock(spec=ConversationRepository)
        mock_conversation = Mock()
        mock_conversation.id = 42
        mock_conversation.parent_conversation_id = None
        repo.create.return_value = mock_conversation
        repo.get_by_id.return_value = mock_conversation
        return repo

    @pytest.fixture
    def mock_exec_manager(self):
        return Mock(spec=ConversationExecutionManager)

    @pytest.mark.asyncio
    async def test_creates_conversation_and_returns_result(
        self, mock_role, mock_agent_config_service, mock_conv_repo, mock_exec_manager
    ):
        """Test that run_sub_agent creates a conversation and returns SubAgentResult with conversation_id."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model = Mock()
        mock_config.model_id = "test-model"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_sub_agent_result = SubAgentResult(result="Review result", conversation_id=42)
        mock_exec_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        result = await run_sub_agent(
            role=mock_role,
            role_type=AgentRoleType.CODE_REVIEW,
            prompt="Review this",
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_entity=make_mock_task(),
            working_dir="/test/working/dir",
            execution_manager=mock_exec_manager,
        )

        assert result == SubAgentResult(result="Review result", conversation_id=42)
        mock_conv_repo.create.assert_called_once()
        create_call_kwargs = mock_conv_repo.create.call_args[1]
        assert create_call_kwargs["is_active"] is False
        assert create_call_kwargs["parent_conversation_id"] is None

    @pytest.mark.asyncio
    async def test_creates_conversation_with_parent_conversation_id(
        self, mock_role, mock_agent_config_service, mock_conv_repo, mock_exec_manager
    ):
        """Test that parent_conversation_id is passed through when creating a conversation."""
        mock_config = Mock(spec=AgentEngineModelConfig)
        mock_config.engine = AgentEngine.INTERNAL
        mock_config.model = Mock()
        mock_config.model_id = "test-model"
        mock_agent_config_service.get_effective_config.return_value = mock_config

        mock_sub_agent_result = SubAgentResult(result="Done", conversation_id=42)
        mock_exec_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        # The created conversation needs parent_conversation_id=123 so validation passes
        mock_conv_repo.get_by_id.return_value.parent_conversation_id = 123

        await run_sub_agent(
            role=mock_role,
            role_type=AgentRoleType.CODE_REVIEW,
            prompt="Review this",
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_entity=make_mock_task(task_id=5),
            working_dir="/test/working/dir",
            execution_manager=mock_exec_manager,
            parent_conversation_id=123,
        )

        create_call_kwargs = mock_conv_repo.create.call_args[1]
        assert create_call_kwargs["parent_conversation_id"] == 123
        assert create_call_kwargs["parent_entity_id"] == 5

    @pytest.mark.asyncio
    async def test_resumes_conversation_by_id(
        self, mock_role, mock_agent_config_service, mock_conv_repo, mock_exec_manager
    ):
        """Test that passing conversation_id resumes existing conversation without creating new one."""
        existing_conversation = Mock()
        existing_conversation.id = 99
        existing_conversation.parent_conversation_id = 123
        mock_conv_repo.get_by_id.return_value = existing_conversation

        mock_sub_agent_result = SubAgentResult(result="Resumed result", conversation_id=99)
        mock_exec_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        result = await run_sub_agent(
            role=mock_role,
            role_type=AgentRoleType.CODE_REVIEW,
            prompt="Review this",
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conv_repo,
            parent_entity=make_mock_task(),
            working_dir="/test/working/dir",
            execution_manager=mock_exec_manager,
            parent_conversation_id=123,
            conversation_id=99,
        )

        assert result == SubAgentResult(result="Resumed result", conversation_id=99)
        mock_conv_repo.create.assert_not_called()
        mock_conv_repo.get_by_id.assert_called_once_with(99)

    @pytest.mark.asyncio
    async def test_resumption_raises_model_retry_for_wrong_parent(
        self, mock_role, mock_agent_config_service, mock_conv_repo, mock_exec_manager
    ):
        """Test that resuming a conversation with wrong parent_conversation_id raises ModelRetry."""
        existing_conversation = Mock()
        existing_conversation.id = 99
        existing_conversation.parent_conversation_id = 999  # Different from expected
        mock_conv_repo.get_by_id.return_value = existing_conversation

        with pytest.raises(ModelRetry, match="does not belong to this conversation context"):
            await run_sub_agent(
                role=mock_role,
                role_type=AgentRoleType.CODE_REVIEW,
                prompt="Review this",
                agent_config_service=mock_agent_config_service,
                conversation_repo=mock_conv_repo,
                parent_entity=make_mock_task(),
                working_dir="/test/working/dir",
                execution_manager=mock_exec_manager,
                parent_conversation_id=123,  # Doesn't match conversation.parent_conversation_id=999
                conversation_id=99,
            )

    @pytest.mark.asyncio
    async def test_resumption_raises_model_retry_for_nonexistent_conversation(
        self, mock_role, mock_agent_config_service, mock_conv_repo, mock_exec_manager
    ):
        """Test that resuming a non-existent conversation raises ModelRetry."""
        mock_conv_repo.get_by_id.return_value = None

        with pytest.raises(ModelRetry, match="not found"):
            await run_sub_agent(
                role=mock_role,
                role_type=AgentRoleType.CODE_REVIEW,
                prompt="Review this",
                agent_config_service=mock_agent_config_service,
                conversation_repo=mock_conv_repo,
                parent_entity=make_mock_task(),
                working_dir="/test/working/dir",
                execution_manager=mock_exec_manager,
                conversation_id=9999,
            )


def _make_stream(*events):
    """Return a synchronous callable that produces an async generator of the given events."""

    async def _gen():
        for event in events:
            yield event

    return Mock(return_value=_gen())


def _make_failing_stream(exc: Exception):
    """Return a synchronous callable that produces an async generator raising exc immediately."""

    async def _gen():
        raise exc
        yield  # makes this an async generator

    return Mock(return_value=_gen())


class TestRunSubAgentExecution:
    """Tests for ConversationExecutionManager.run_sub_agent_execution."""

    @pytest.fixture
    def manager(self):
        return ConversationExecutionManager()

    @pytest.fixture
    def mock_conversation(self):
        conv = Mock()
        conv.id = 42
        return conv

    @pytest.fixture
    def mock_role(self):
        from devboard.agents.roles.base import AgentRole

        return Mock(spec=AgentRole)

    @pytest.fixture
    def mock_conv_repo(self):
        return Mock(spec=ConversationRepository)

    @pytest.fixture
    def mock_agent_config_service(self):
        return Mock(spec=AgentConfigService)

    @pytest.mark.asyncio
    async def test_successful_execution_returns_result(
        self, manager, mock_conversation, mock_role, mock_conv_repo, mock_agent_config_service
    ):
        """Test that successful execution returns SubAgentResult with last text content."""
        final_message = TextMessage(
            role=MessageRole.AGENT, text_content="Sub-agent result", timestamp=datetime.datetime.now()
        )
        mock_exec_service = Mock()
        mock_exec_service.stream_events_for_message_or_approval = _make_stream(final_message)

        with patch(
            "devboard.agents.execution.manager.create_agent_execution_service",
            return_value=mock_exec_service,
        ):
            result = await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=mock_role,
                prompt="Do something",
                conversation_repo=mock_conv_repo,
                agent_config_service=mock_agent_config_service,
                working_dir="/test/dir",
            )

        assert result == SubAgentResult(result="Sub-agent result", conversation_id=42)
        assert 42 not in manager._executions
        # commit after event + final commit = 2
        assert mock_conv_repo.commit.call_count == 2

    @pytest.mark.asyncio
    async def test_registers_execution_as_sub_agent(
        self, manager, mock_conversation, mock_role, mock_conv_repo, mock_agent_config_service
    ):
        """Test that the execution is registered with is_sub_agent=True during streaming."""
        captured_execution = {}

        async def capturing_stream():
            captured_execution["exec"] = manager._executions.get(42)
            yield TextMessage(role=MessageRole.AGENT, text_content="result", timestamp=datetime.datetime.now())

        mock_exec_service = Mock()
        mock_exec_service.stream_events_for_message_or_approval = Mock(return_value=capturing_stream())

        with patch(
            "devboard.agents.execution.manager.create_agent_execution_service",
            return_value=mock_exec_service,
        ):
            await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=mock_role,
                prompt="Do something",
                conversation_repo=mock_conv_repo,
                agent_config_service=mock_agent_config_service,
                working_dir="/test/dir",
            )

        exec_entry = captured_execution.get("exec")
        assert exec_entry is not None
        assert exec_entry.is_sub_agent is True
        assert exec_entry.status == ExecutionStatus.RUNNING

    @pytest.mark.asyncio
    async def test_raises_conversation_busy_error_when_already_running(
        self, manager, mock_conversation, mock_role, mock_conv_repo, mock_agent_config_service
    ):
        """Test that ConversationBusyError is raised if conversation already has active execution."""
        from devboard.agents.execution.types import ConversationExecution

        existing = ConversationExecution(
            conversation_id=42,
            interrupt_requested=asyncio.Event(),
            asyncio_task=Mock(),
            status=ExecutionStatus.RUNNING,
            started_at=datetime.datetime.now(datetime.UTC),
        )
        manager._executions[42] = existing

        with pytest.raises(ConversationBusyError):
            await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=mock_role,
                prompt="Do something",
                conversation_repo=mock_conv_repo,
                agent_config_service=mock_agent_config_service,
                working_dir="/test/dir",
            )

    @pytest.mark.asyncio
    async def test_execution_cleaned_up_after_failure(
        self, manager, mock_conversation, mock_role, mock_conv_repo, mock_agent_config_service
    ):
        """Test that execution is removed from _executions even when streaming raises."""
        mock_exec_service = Mock()
        mock_exec_service.stream_events_for_message_or_approval = _make_failing_stream(RuntimeError("Agent failed"))

        with patch(
            "devboard.agents.execution.manager.create_agent_execution_service",
            return_value=mock_exec_service,
        ):
            with pytest.raises(RuntimeError, match="Agent failed"):
                await manager.run_sub_agent_execution(
                    conversation=mock_conversation,
                    role=mock_role,
                    prompt="Do something",
                    conversation_repo=mock_conv_repo,
                    agent_config_service=mock_agent_config_service,
                    working_dir="/test/dir",
                )

        assert 42 not in manager._executions

    @pytest.mark.asyncio
    async def test_interrupt_event_is_signalable_via_request_interrupt(
        self, manager, mock_conversation, mock_role, mock_conv_repo, mock_agent_config_service
    ):
        """Test that request_interrupt() signals the sub-agent's interrupt event during streaming."""
        interrupt_was_set = {}

        async def signaling_stream():
            exec_entry = manager._executions.get(42)
            assert exec_entry is not None
            manager.request_interrupt(42)
            interrupt_was_set["value"] = exec_entry.interrupt_requested.is_set()
            yield TextMessage(role=MessageRole.AGENT, text_content="result", timestamp=datetime.datetime.now())

        mock_exec_service = Mock()
        mock_exec_service.stream_events_for_message_or_approval = Mock(return_value=signaling_stream())

        with patch(
            "devboard.agents.execution.manager.create_agent_execution_service",
            return_value=mock_exec_service,
        ):
            await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=mock_role,
                prompt="Do something",
                conversation_repo=mock_conv_repo,
                agent_config_service=mock_agent_config_service,
                working_dir="/test/dir",
            )

        assert interrupt_was_set.get("value") is True


def _make_file(
    path: str,
    content: str = "line\n",
    additions: int = 1,
    deletions: int = 0,
    is_new: bool = False,
    is_deleted: bool = False,
) -> FileDiff:
    return FileDiff(
        file_path=path,
        diff_content=content,
        additions=additions,
        deletions=deletions,
        is_new_file=is_new,
        is_deleted=is_deleted,
    )


def _make_diff(*files: FileDiff) -> StructuredDiff:
    return StructuredDiff(
        files=list(files),
        additions=sum(f.additions for f in files),
        deletions=sum(f.deletions for f in files),
    )


class TestBuildCodeReviewPrompt:
    """Tests for build_code_review_prompt diff filtering and truncation."""

    def test_normal_file_under_limit_is_included_verbatim(self):
        content = "+" + "\n+".join(["line"] * 10)
        file = _make_file("src/foo.py", content, additions=10)
        prompt = build_code_review_prompt(_make_diff(file))
        assert content in prompt

    def test_lock_file_diff_replaced_with_stub(self):
        file = _make_file("uv.lock", "+lots of locked content\n" * 100, additions=100)
        prompt = build_code_review_prompt(_make_diff(file))
        assert "+lots of locked content" not in prompt
        assert "uv.lock" in prompt
        assert "lock/generated file" in prompt

    def test_nested_lock_file_excluded(self):
        file = _make_file("backend/uv.lock", "+content\n", additions=1)
        prompt = build_code_review_prompt(_make_diff(file))
        assert "+content" not in prompt
        assert "lock/generated file" in prompt

    def test_per_file_truncation_at_limit(self):
        # Use a distinctive sentinel after the cut point so we can verify it's absent.
        kept = "a" * _MAX_FILE_DIFF_CHARS
        overflow = "OVERFLOW_SENTINEL"
        long_content = kept + overflow
        file = _make_file("src/big.py", long_content, additions=1)
        prompt = build_code_review_prompt(_make_diff(file))
        assert "characters truncated" in prompt
        assert kept[:100] in prompt  # start of kept content is present
        assert overflow not in prompt  # sentinel beyond the limit is absent

    def test_file_exactly_at_limit_is_not_truncated(self):
        content = "x" * _MAX_FILE_DIFF_CHARS
        file = _make_file("src/exact.py", content, additions=1)
        prompt = build_code_review_prompt(_make_diff(file))
        assert "characters truncated" not in prompt

    def test_deleted_file_diff_replaced_with_stub(self):
        file = _make_file("src/old.py", "-lots of deleted content\n" * 50, deletions=50, is_deleted=True)
        prompt = build_code_review_prompt(_make_diff(file))
        assert "-lots of deleted content" not in prompt
        assert "src/old.py" in prompt
        assert "[File deleted]" in prompt

    def test_new_files_included_when_under_global_budget(self):
        new_file = _make_file("src/new.py", "+hello\n", additions=1, is_new=True)
        prompt = build_code_review_prompt(_make_diff(new_file))
        assert "+hello" in prompt
        assert "omitted from the diff" not in prompt

    def test_new_files_dropped_when_global_budget_exceeded(self):
        # Create enough modified files to exceed _MAX_TOTAL_DIFF_CHARS after per-file truncation.
        # Each modified file contributes _MAX_FILE_DIFF_CHARS chars; we need enough to fill the budget.
        files_needed = _MAX_TOTAL_DIFF_CHARS // _MAX_FILE_DIFF_CHARS + 1
        big_content = "x" * (_MAX_FILE_DIFF_CHARS + 100)  # over per-file limit → truncated to _MAX_FILE_DIFF_CHARS
        modified_files = [_make_file(f"src/modified_{i}.py", big_content, additions=1) for i in range(files_needed)]
        new_file = _make_file("src/brand_new.py", "+new content\n", additions=1, is_new=True)

        prompt = build_code_review_prompt(_make_diff(*modified_files, new_file))

        assert "+new content" not in prompt
        assert "src/brand_new.py" in prompt
        assert "omitted from the diff" in prompt

    def test_modified_files_always_included_when_budget_exceeded(self):
        files_needed = _MAX_TOTAL_DIFF_CHARS // _MAX_FILE_DIFF_CHARS + 1
        big_content = "x" * (_MAX_FILE_DIFF_CHARS + 100)
        modified_files = [_make_file(f"src/modified_{i}.py", big_content, additions=1) for i in range(files_needed)]
        new_file = _make_file("src/new.py", "+new\n", additions=1, is_new=True)

        prompt = build_code_review_prompt(_make_diff(*modified_files, new_file))

        # All modified file headers should be present
        for i in range(files_needed):
            assert f"src/modified_{i}.py" in prompt

    def test_additional_context_appended(self):
        file = _make_file("src/foo.py", "+x\n", additions=1)
        prompt = build_code_review_prompt(_make_diff(file), additional_context="Pay attention to security.")
        assert "Pay attention to security." in prompt
