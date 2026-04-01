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
from devboard.agents.roles import AgentRoleType
from devboard.agents.tools.sub_agent_tools import (
    CodebaseInvestigationContext,
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
        """Test that successful execution returns SubAgentResult and pops from _executions."""
        final_message = TextMessage(
            role=MessageRole.AGENT, text_content="Sub-agent result", timestamp=datetime.datetime.now()
        )
        mock_exec_service = AsyncMock()
        mock_exec_service.send_message_or_approval.return_value = final_message

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
        # Execution should be cleaned up from _executions after completion
        assert 42 not in manager._executions
        mock_conv_repo.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_registers_execution_as_sub_agent(
        self, manager, mock_conversation, mock_role, mock_conv_repo, mock_agent_config_service
    ):
        """Test that the execution is registered with is_sub_agent=True."""
        captured_execution = {}

        async def capture_and_return(prompt):
            # At this point, the execution should be registered
            captured_execution["exec"] = manager._executions.get(42)
            final_message = TextMessage(
                role=MessageRole.AGENT, text_content="result", timestamp=datetime.datetime.now()
            )
            return final_message

        mock_exec_service = AsyncMock()
        mock_exec_service.send_message_or_approval.side_effect = capture_and_return

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

        # Manually register an active execution
        mock_event = asyncio.Event()
        mock_task = Mock()
        existing = ConversationExecution(
            conversation_id=42,
            interrupt_requested=mock_event,
            asyncio_task=mock_task,
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
        """Test that execution is removed from _executions even when send_message_or_approval raises."""
        mock_exec_service = AsyncMock()
        mock_exec_service.send_message_or_approval.side_effect = RuntimeError("Agent failed")

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
        """Test that request_interrupt() signals the sub-agent's interrupt event."""
        interrupt_was_set = {}

        async def slow_execution(prompt):
            # Allow the test to signal interrupt while "running"
            exec_entry = manager._executions.get(42)
            assert exec_entry is not None
            # Signal the interrupt
            manager.request_interrupt(42)
            interrupt_was_set["value"] = exec_entry.interrupt_requested.is_set()
            final_message = TextMessage(
                role=MessageRole.AGENT, text_content="result", timestamp=datetime.datetime.now()
            )
            return final_message

        mock_exec_service = AsyncMock()
        mock_exec_service.send_message_or_approval.side_effect = slow_execution

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
