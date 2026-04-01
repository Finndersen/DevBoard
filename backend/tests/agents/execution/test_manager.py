"""Tests for _emit_agent_run_event in ConversationExecutionManager module."""

from unittest.mock import Mock, patch

import pytest

from devboard.agents.execution.manager import _emit_agent_run_event
from devboard.agents.execution.types import ExecutionStatus
from devboard.agents.roles import AgentRoleType
from devboard.db.models import Project, Task


class TestEmitAgentRunEvent:
    @pytest.fixture
    def mock_task_conversation(self):
        task = Mock(spec=Task)
        task.id = 10
        task.project_id = 5
        conv = Mock()
        conv.id = 42
        conv.agent_role = AgentRoleType.TASK_IMPLEMENTATION
        conv.get_parent_entity.return_value = task
        return conv

    @pytest.fixture
    def mock_project_conversation(self):
        project = Mock(spec=Project)
        project.id = 5
        conv = Mock()
        conv.id = 99
        conv.agent_role = AgentRoleType.PROJECT
        conv.get_parent_entity.return_value = project
        return conv

    @pytest.fixture
    def mock_session(self):
        return Mock()

    def _patch_manager(self, mock_session, conversation):
        return [
            patch("devboard.agents.execution.manager.SessionLocal", return_value=mock_session),
            patch(
                "devboard.agents.execution.manager.ConversationRepository",
                return_value=Mock(get_by_id=Mock(return_value=conversation)),
            ),
            patch("devboard.agents.execution.manager.LogEntryRepository"),
            patch("devboard.agents.execution.manager.SystemEventEmitter"),
        ]

    @pytest.mark.asyncio
    async def test_task_conversation_emits_with_project_and_task_ids(self, mock_task_conversation, mock_session):
        with (
            patch("devboard.agents.execution.manager.SessionLocal", return_value=mock_session),
            patch(
                "devboard.agents.execution.manager.ConversationRepository",
                return_value=Mock(get_by_id=Mock(return_value=mock_task_conversation)),
            ),
            patch("devboard.agents.execution.manager.LogEntryRepository"),
            patch("devboard.agents.execution.manager.SystemEventEmitter") as mock_emitter_cls,
        ):
            mock_emitter = Mock()
            mock_emitter_cls.return_value = mock_emitter

            await _emit_agent_run_event(42, ExecutionStatus.COMPLETED, None)

            mock_emitter.emit_agent_run_completed.assert_called_once_with(
                conversation_id=42,
                agent_role=AgentRoleType.TASK_IMPLEMENTATION.value,
                status="completed",
                project_id=5,
                task_id=10,
                error=None,
            )

    @pytest.mark.asyncio
    async def test_project_conversation_omits_task_id(self, mock_project_conversation, mock_session):
        with (
            patch("devboard.agents.execution.manager.SessionLocal", return_value=mock_session),
            patch(
                "devboard.agents.execution.manager.ConversationRepository",
                return_value=Mock(get_by_id=Mock(return_value=mock_project_conversation)),
            ),
            patch("devboard.agents.execution.manager.LogEntryRepository"),
            patch("devboard.agents.execution.manager.SystemEventEmitter") as mock_emitter_cls,
        ):
            mock_emitter = Mock()
            mock_emitter_cls.return_value = mock_emitter

            await _emit_agent_run_event(99, ExecutionStatus.INTERRUPTED, None)

            mock_emitter.emit_agent_run_completed.assert_called_once_with(
                conversation_id=99,
                agent_role=AgentRoleType.PROJECT.value,
                status="interrupted",
                project_id=5,
                task_id=None,
                error=None,
            )

    @pytest.mark.asyncio
    async def test_failed_status_passes_error_message(self, mock_task_conversation, mock_session):
        with (
            patch("devboard.agents.execution.manager.SessionLocal", return_value=mock_session),
            patch(
                "devboard.agents.execution.manager.ConversationRepository",
                return_value=Mock(get_by_id=Mock(return_value=mock_task_conversation)),
            ),
            patch("devboard.agents.execution.manager.LogEntryRepository"),
            patch("devboard.agents.execution.manager.SystemEventEmitter") as mock_emitter_cls,
        ):
            mock_emitter = Mock()
            mock_emitter_cls.return_value = mock_emitter

            await _emit_agent_run_event(42, ExecutionStatus.FAILED, "Agent timed out")

            mock_emitter.emit_agent_run_completed.assert_called_once_with(
                conversation_id=42,
                agent_role=AgentRoleType.TASK_IMPLEMENTATION.value,
                status="failed",
                project_id=5,
                task_id=10,
                error="Agent timed out",
            )

    @pytest.mark.asyncio
    async def test_missing_conversation_does_not_emit(self, mock_session):
        with (
            patch("devboard.agents.execution.manager.SessionLocal", return_value=mock_session),
            patch(
                "devboard.agents.execution.manager.ConversationRepository",
                return_value=Mock(get_by_id=Mock(return_value=None)),
            ),
            patch("devboard.agents.execution.manager.SystemEventEmitter") as mock_emitter_cls,
        ):
            mock_emitter = Mock()
            mock_emitter_cls.return_value = mock_emitter

            await _emit_agent_run_event(999999, ExecutionStatus.COMPLETED, None)

            mock_emitter.emit_agent_run_completed.assert_not_called()
