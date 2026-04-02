"""Tests for ConversationExecutionManager and related helpers."""

import asyncio
import datetime
from unittest.mock import Mock, patch

import pytest

from devboard.agents.events import ExecutionCompleteEvent, MessageRole, TextMessage
from devboard.agents.exceptions import AgentInterruptedError
from devboard.agents.execution.manager import ConversationExecutionManager, _emit_agent_run_event
from devboard.agents.execution.types import ConversationExecution, ExecutionStatus
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


async def _async_gen(*events):
    for event in events:
        yield event


class TestRunSubAgentExecution:
    @pytest.fixture
    def manager(self):
        return ConversationExecutionManager()

    @pytest.fixture
    def mock_conversation(self):
        conv = Mock()
        conv.id = 42
        return conv

    @pytest.fixture
    def mock_execution_service(self):
        return Mock()

    def _patch_create_service(self, mock_execution_service):
        return patch(
            "devboard.agents.execution.manager.create_agent_execution_service",
            return_value=mock_execution_service,
        )

    def _make_text_event(self) -> TextMessage:
        return TextMessage(
            text_content="done",
            role=MessageRole.AGENT,
            timestamp=datetime.datetime.now(datetime.UTC),
        )

    @pytest.mark.asyncio
    async def test_events_committed_and_broadcast(self, manager, mock_conversation, mock_execution_service):
        """Each event from stream is committed and put on broadcast_queue; ExecutionCompleteEvent sent after."""
        text_event = self._make_text_event()
        mock_execution_service.stream_events_for_message_or_approval = Mock(return_value=_async_gen(text_event))
        mock_conversation_repo = Mock()

        with self._patch_create_service(mock_execution_service):
            result = await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=Mock(),
                prompt="do the thing",
                conversation_repo=mock_conversation_repo,
                agent_config_service=Mock(),
                working_dir="/tmp",
            )

        # Text event + ExecutionCompleteEvent
        assert manager.broadcast_queue.qsize() == 2
        conv_id_1, event_1 = manager.broadcast_queue.get_nowait()
        conv_id_2, event_2 = manager.broadcast_queue.get_nowait()
        assert conv_id_1 == 42
        assert event_1 is text_event
        assert conv_id_2 == 42
        assert isinstance(event_2, ExecutionCompleteEvent)
        assert event_2.status == "completed"
        # commit called after each event + final commit = 2 total
        assert mock_conversation_repo.commit.call_count == 2
        assert result.result == "done"
        assert result.conversation_id == 42

    @pytest.mark.asyncio
    async def test_stale_completed_entry_restored_after_sub_agent_completes(
        self, manager, mock_conversation, mock_execution_service
    ):
        """A previous non-running entry for the conversation is restored after the sub-agent finishes."""
        stale_exec = ConversationExecution(
            conversation_id=42,
            interrupt_requested=asyncio.Event(),
            asyncio_task=Mock(),
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.datetime.now(datetime.UTC),
        )
        manager._executions[42] = stale_exec
        mock_execution_service.stream_events_for_message_or_approval = Mock(return_value=_async_gen())

        with self._patch_create_service(mock_execution_service):
            await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=Mock(),
                prompt="do the thing",
                conversation_repo=Mock(),
                agent_config_service=Mock(),
                working_dir="/tmp",
            )

        assert manager._executions[42] is stale_exec

    @pytest.mark.asyncio
    async def test_stale_entry_restored_when_agent_interrupted(
        self, manager, mock_conversation, mock_execution_service
    ):
        """A previous non-running entry is restored even when AgentInterruptedError propagates."""
        stale_exec = ConversationExecution(
            conversation_id=42,
            interrupt_requested=asyncio.Event(),
            asyncio_task=Mock(),
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.datetime.now(datetime.UTC),
        )
        manager._executions[42] = stale_exec

        async def interrupted_stream():
            raise AgentInterruptedError()
            yield  # makes this an async generator

        mock_execution_service.stream_events_for_message_or_approval = Mock(return_value=interrupted_stream())

        with self._patch_create_service(mock_execution_service):
            with pytest.raises(AgentInterruptedError):
                await manager.run_sub_agent_execution(
                    conversation=mock_conversation,
                    role=Mock(),
                    prompt="do the thing",
                    conversation_repo=Mock(),
                    agent_config_service=Mock(),
                    working_dir="/tmp",
                )

        assert manager._executions[42] is stale_exec

    @pytest.mark.asyncio
    async def test_no_prior_entry_removed_on_completion(self, manager, mock_conversation, mock_execution_service):
        """When there is no prior entry, _executions entry is removed after sub-agent completes."""
        mock_execution_service.stream_events_for_message_or_approval = Mock(return_value=_async_gen())

        with self._patch_create_service(mock_execution_service):
            await manager.run_sub_agent_execution(
                conversation=mock_conversation,
                role=Mock(),
                prompt="do the thing",
                conversation_repo=Mock(),
                agent_config_service=Mock(),
                working_dir="/tmp",
            )

        assert 42 not in manager._executions

    @pytest.mark.asyncio
    async def test_no_execution_complete_event_broadcast_when_interrupted(
        self, manager, mock_conversation, mock_execution_service
    ):
        """No ExecutionCompleteEvent is put on broadcast_queue when AgentInterruptedError is raised."""

        async def interrupted_stream():
            raise AgentInterruptedError()
            yield  # makes this an async generator

        mock_execution_service.stream_events_for_message_or_approval = Mock(return_value=interrupted_stream())

        with self._patch_create_service(mock_execution_service):
            with pytest.raises(AgentInterruptedError):
                await manager.run_sub_agent_execution(
                    conversation=mock_conversation,
                    role=Mock(),
                    prompt="do the thing",
                    conversation_repo=Mock(),
                    agent_config_service=Mock(),
                    working_dir="/tmp",
                )

        assert manager.broadcast_queue.empty()
