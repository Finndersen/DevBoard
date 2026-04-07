"""Tests for task agent tools (send_task_agent_prompt, get_task_agent_status)."""

import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.tools.task_agent_tools import (
    create_get_task_agent_status_tool,
    create_send_task_agent_prompt_tool,
)
from devboard.db.models import Conversation, Project, Task, TaskStatus
from devboard.db.repositories.conversation import ConversationRepository, NoActiveConversationError
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_project():
    project = Mock(spec=Project)
    project.id = 1
    project.name = "Test Project"
    return project


@pytest.fixture
def mock_task():
    task = Mock(spec=Task)
    task.id = 42
    task.project_id = 1
    task.status = TaskStatus.PLANNING
    return task


@pytest.fixture
def mock_task_service(mock_task):
    service = Mock(spec=TaskService)
    service.get_task_by_id.return_value = mock_task
    return service


@pytest.fixture
def mock_conversation():
    conv = Mock(spec=Conversation)
    conv.id = 99
    conv.agent_role = Mock()
    conv.agent_role.value = "task_planning"
    return conv


@pytest.fixture
def mock_conversation_repo(mock_conversation):
    repo = Mock(spec=ConversationRepository)
    repo.get_active_conversation_for_entity.return_value = mock_conversation
    return repo


def make_text_message(role: MessageRole, text: str, offset_seconds: int = 0) -> TextMessage:
    return TextMessage(
        role=role,
        text_content=text,
        timestamp=datetime.datetime(2024, 1, 1, 12, 0, offset_seconds, tzinfo=datetime.UTC),
    )


class TestSendTaskAgentPrompt:
    """Tests for create_send_task_agent_prompt_tool."""

    @pytest.mark.asyncio
    async def test_rejects_task_not_in_project(self, mock_project, mock_task_service, mock_conversation_repo):
        """Raises ModelRetry if task belongs to a different project."""
        other_task = Mock(spec=Task)
        other_task.id = 42
        other_task.project_id = 999
        other_task.status = TaskStatus.PLANNING
        mock_task_service.get_task_by_id.return_value = other_task

        tool = create_send_task_agent_prompt_tool(mock_project, mock_task_service, mock_conversation_repo)

        with pytest.raises(ModelRetry, match="does not belong to this project"):
            await tool.function(task_id=42, message="Do something")

    @pytest.mark.asyncio
    async def test_rejects_task_not_found(self, mock_project, mock_task_service, mock_conversation_repo):
        """Raises ModelRetry if task is not found."""
        mock_task_service.get_task_by_id.return_value = None

        tool = create_send_task_agent_prompt_tool(mock_project, mock_task_service, mock_conversation_repo)

        with pytest.raises(ModelRetry, match="not found"):
            await tool.function(task_id=999, message="Do something")

    @pytest.mark.asyncio
    async def test_rejects_completed_task(self, mock_project, mock_task_service, mock_conversation_repo):
        """Raises ModelRetry if the task is already complete."""
        completed_task = Mock(spec=Task)
        completed_task.id = 42
        completed_task.project_id = 1
        completed_task.status = TaskStatus.COMPLETE
        mock_task_service.get_task_by_id.return_value = completed_task

        tool = create_send_task_agent_prompt_tool(mock_project, mock_task_service, mock_conversation_repo)

        with pytest.raises(ModelRetry, match="already complete"):
            await tool.function(task_id=42, message="Do something")

    @pytest.mark.asyncio
    async def test_returns_error_when_no_active_conversation(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """Returns error string when no active conversation exists for the task."""
        mock_conversation_repo.get_active_conversation_for_entity.side_effect = NoActiveConversationError(
            "No active conversation"
        )

        tool = create_send_task_agent_prompt_tool(mock_project, mock_task_service, mock_conversation_repo)

        result = await tool.function(task_id=42, message="Do something")

        assert "No active conversation" in result
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_returns_error_when_agent_already_running(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """Returns error string when the agent execution is already running."""
        tool = create_send_task_agent_prompt_tool(mock_project, mock_task_service, mock_conversation_repo)

        with patch("devboard.agents.tools.task_agent_tools.get_execution_manager") as mock_get_mgr:
            mock_exec_manager = Mock()
            mock_exec_manager.has_active_execution.return_value = True
            mock_get_mgr.return_value = mock_exec_manager

            result = await tool.function(task_id=42, message="Do something")

        assert "already running" in result
        assert "Error" in result
        mock_exec_manager.start_agent_execution.assert_not_called()

    @pytest.mark.asyncio
    async def test_starts_execution_and_returns_running_status(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """Successfully starts execution and returns confirmation with running status."""
        tool = create_send_task_agent_prompt_tool(mock_project, mock_task_service, mock_conversation_repo)

        with patch("devboard.agents.tools.task_agent_tools.get_execution_manager") as mock_get_mgr:
            mock_exec_manager = Mock()
            mock_exec_manager.has_active_execution.return_value = False
            mock_get_mgr.return_value = mock_exec_manager

            result = await tool.function(task_id=42, message="Write the spec")

        assert "task_id: 42" in result
        assert "conversation_id: 99" in result
        assert "status: running" in result
        mock_exec_manager.start_agent_execution.assert_called_once_with(99, "Write the spec")


class TestGetTaskAgentStatus:
    """Tests for create_get_task_agent_status_tool."""

    @pytest.mark.asyncio
    async def test_returns_error_for_task_not_in_project(self, mock_project, mock_task_service, mock_conversation_repo):
        """Raises ModelRetry if task belongs to a different project."""
        other_task = Mock(spec=Task)
        other_task.id = 42
        other_task.project_id = 999
        mock_task_service.get_task_by_id.return_value = other_task

        tool = create_get_task_agent_status_tool(mock_project, mock_task_service, mock_conversation_repo)

        with pytest.raises(ModelRetry, match="does not belong to this project"):
            await tool.function(task_id=42)

    @pytest.mark.asyncio
    async def test_returns_error_for_task_not_found(self, mock_project, mock_task_service, mock_conversation_repo):
        """Raises ModelRetry if task is not found."""
        mock_task_service.get_task_by_id.return_value = None

        tool = create_get_task_agent_status_tool(mock_project, mock_task_service, mock_conversation_repo)

        with pytest.raises(ModelRetry, match="not found"):
            await tool.function(task_id=999)

    @pytest.mark.asyncio
    async def test_handles_no_active_conversation(self, mock_project, mock_task_service, mock_conversation_repo):
        """Returns error string when no active conversation exists."""
        mock_conversation_repo.get_active_conversation_for_entity.side_effect = NoActiveConversationError(
            "No active conversation"
        )

        tool = create_get_task_agent_status_tool(mock_project, mock_task_service, mock_conversation_repo)

        result = await tool.function(task_id=42)

        assert "No active conversation" in result
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_returns_idle_status_with_messages(self, mock_project, mock_task_service, mock_conversation_repo):
        """Returns idle status and recent messages when no execution is running."""
        messages = [
            make_text_message(MessageRole.USER, "Write the spec", offset_seconds=0),
            make_text_message(MessageRole.AGENT, "I have written the spec.", offset_seconds=10),
        ]

        mock_history_service = Mock()
        mock_history_service.get_conversation_history = AsyncMock(return_value=Mock(messages=messages))

        tool = create_get_task_agent_status_tool(mock_project, mock_task_service, mock_conversation_repo)

        with (
            patch("devboard.agents.tools.task_agent_tools.get_execution_manager") as mock_get_mgr,
            patch(
                "devboard.agents.tools.task_agent_tools.create_conversation_history_service",
                return_value=mock_history_service,
            ),
        ):
            mock_exec_manager = Mock()
            mock_exec_manager.has_active_execution.return_value = False
            mock_get_mgr.return_value = mock_exec_manager

            result = await tool.function(task_id=42)

        assert "status: idle" in result
        assert "task_id: 42" in result
        assert "conversation_id: 99" in result
        assert "agent_role: task_planning" in result
        assert "Write the spec" in result
        assert "I have written the spec." in result
        assert "[user]" in result
        assert "[assistant]" in result

    @pytest.mark.asyncio
    async def test_returns_running_status_when_execution_active(
        self, mock_project, mock_task_service, mock_conversation_repo
    ):
        """Returns running status when an execution is active."""
        mock_history_service = Mock()
        mock_history_service.get_conversation_history = AsyncMock(return_value=Mock(messages=[]))

        tool = create_get_task_agent_status_tool(mock_project, mock_task_service, mock_conversation_repo)

        with (
            patch("devboard.agents.tools.task_agent_tools.get_execution_manager") as mock_get_mgr,
            patch(
                "devboard.agents.tools.task_agent_tools.create_conversation_history_service",
                return_value=mock_history_service,
            ),
        ):
            mock_exec_manager = Mock()
            mock_exec_manager.has_active_execution.return_value = True
            mock_get_mgr.return_value = mock_exec_manager

            result = await tool.function(task_id=42)

        assert "status: running" in result

    @pytest.mark.asyncio
    async def test_respects_max_messages_limit(self, mock_project, mock_task_service, mock_conversation_repo):
        """Only returns the last N messages according to max_messages."""
        messages = [make_text_message(MessageRole.USER, f"Message {i}", offset_seconds=i) for i in range(10)]

        mock_history_service = Mock()
        mock_history_service.get_conversation_history = AsyncMock(return_value=Mock(messages=messages))

        tool = create_get_task_agent_status_tool(mock_project, mock_task_service, mock_conversation_repo)

        with (
            patch("devboard.agents.tools.task_agent_tools.get_execution_manager") as mock_get_mgr,
            patch(
                "devboard.agents.tools.task_agent_tools.create_conversation_history_service",
                return_value=mock_history_service,
            ),
        ):
            mock_exec_manager = Mock()
            mock_exec_manager.has_active_execution.return_value = False
            mock_get_mgr.return_value = mock_exec_manager

            result = await tool.function(task_id=42, max_messages=3)

        # Should only include last 3 messages (7, 8, 9)
        assert "Message 9" in result
        assert "Message 8" in result
        assert "Message 7" in result
        assert "Message 0" not in result
        assert "recent_messages (3)" in result
