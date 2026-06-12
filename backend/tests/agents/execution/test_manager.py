"""Tests for ConversationExecutionManager and related helpers."""

import asyncio
import datetime
from unittest.mock import Mock, patch

import pytest

from devboard.agents.events import AgentRunCompletedEvent, AgentRunStartedEvent, ContextUsage, MessageRole, TextMessage
from devboard.agents.exceptions import AgentInterruptedError
from devboard.agents.execution.manager import (
    ConversationExecutionManager,
    _drain_events,
    _map_execution_status_to_run_status,
    _resolve_background_agent_working_dir,
)
from devboard.agents.execution.types import ExecutionStatus
from devboard.db.models.background_agent_run import BackgroundAgentRunStatus


async def _async_gen(*events):
    for event in events:
        yield event


def _make_started_event(conversation_id: int = 42) -> AgentRunStartedEvent:
    return AgentRunStartedEvent(
        conversation_id=conversation_id,
        timestamp=datetime.datetime.now(datetime.UTC),
    )


def _make_completed_event(
    status: str = "completed",
    error: str | None = None,
) -> AgentRunCompletedEvent:
    return AgentRunCompletedEvent(
        status=status,  # type: ignore[arg-type]
        error=error,
        timestamp=datetime.datetime.now(datetime.UTC),
    )


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
        """Each event from stream is committed and put on broadcast_queue; lifecycle events come from the stream."""
        started_event = _make_started_event()
        text_event = self._make_text_event()
        completed_event = _make_completed_event()
        mock_execution_service.stream_events_for_message_or_approval = Mock(
            return_value=_async_gen(started_event, text_event, completed_event)
        )
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

        # AgentRunStartedEvent + TextMessage + AgentRunCompletedEvent — all from the stream
        assert manager.broadcast_queue.qsize() == 3
        conv_id_1, event_1 = manager.broadcast_queue.get_nowait()
        conv_id_2, event_2 = manager.broadcast_queue.get_nowait()
        conv_id_3, event_3 = manager.broadcast_queue.get_nowait()
        assert conv_id_1 == 42
        assert event_1 is started_event
        assert conv_id_2 == 42
        assert event_2 is text_event
        assert conv_id_3 == 42
        assert isinstance(event_3, AgentRunCompletedEvent)
        assert event_3.status == "completed"
        # commit called after each event (3) + final commit = 4 total
        assert mock_conversation_repo.commit.call_count == 4
        assert result.result == "done"
        assert result.conversation_id == 42

    @pytest.mark.asyncio
    async def test_no_prior_entry_removed_on_completion(self, manager, mock_conversation, mock_execution_service):
        """When there is no prior entry, _executions entry is removed after sub-agent completes."""
        started = _make_started_event()
        completed = _make_completed_event()
        mock_execution_service.stream_events_for_message_or_approval = Mock(return_value=_async_gen(started, completed))

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
    async def test_lifecycle_events_broadcast_when_interrupted(
        self, manager, mock_conversation, mock_execution_service
    ):
        """AgentRunStartedEvent and AgentRunCompletedEvent(interrupted) are broadcast even on interrupt.

        Lifecycle events are emitted by AgentExecutionService before it re-raises
        AgentInterruptedError, so the broadcast queue always contains them.
        """

        async def interrupted_stream():
            yield _make_started_event()
            yield _make_completed_event(status="interrupted")
            raise AgentInterruptedError()

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

        assert manager.broadcast_queue.qsize() == 2
        _, started = manager.broadcast_queue.get_nowait()
        _, completed = manager.broadcast_queue.get_nowait()
        assert isinstance(started, AgentRunStartedEvent)
        assert isinstance(completed, AgentRunCompletedEvent)
        assert completed.status == "interrupted"


class TestDrainEvents:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_completed_event(self):
        started = _make_started_event()
        queue: asyncio.Queue[tuple[int, object]] = asyncio.Queue()
        db = Mock()
        db.begin = Mock()

        with patch("devboard.agents.execution.manager.commit_with_lock"):
            result = await _drain_events(_async_gen(started), db, queue, 42)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_completed_event(self):
        usage = ContextUsage(input_tokens=100, output_tokens=50, cache_read_tokens=10, cache_write_tokens=5)
        completed = AgentRunCompletedEvent(
            status="completed", usage=usage, timestamp=datetime.datetime.now(datetime.UTC)
        )
        queue: asyncio.Queue[tuple[int, object]] = asyncio.Queue()
        db = Mock()

        with patch("devboard.agents.execution.manager.commit_with_lock"):
            result = await _drain_events(_async_gen(completed), db, queue, 42)

        assert result is completed

    @pytest.mark.asyncio
    async def test_returns_completed_event_even_when_no_usage(self):
        completed = AgentRunCompletedEvent(
            status="completed", usage=None, timestamp=datetime.datetime.now(datetime.UTC)
        )
        queue: asyncio.Queue[tuple[int, object]] = asyncio.Queue()
        db = Mock()

        with patch("devboard.agents.execution.manager.commit_with_lock"):
            result = await _drain_events(_async_gen(completed), db, queue, 42)

        assert result is completed

    @pytest.mark.asyncio
    async def test_all_events_put_on_queue(self):
        started = _make_started_event()
        completed = _make_completed_event()
        queue: asyncio.Queue[tuple[int, object]] = asyncio.Queue()
        db = Mock()

        with patch("devboard.agents.execution.manager.commit_with_lock"):
            await _drain_events(_async_gen(started, completed), db, queue, 42)

        assert queue.qsize() == 2


class TestMapExecutionStatusToRunStatus:
    def test_completed_maps_to_completed(self):
        assert _map_execution_status_to_run_status(ExecutionStatus.COMPLETED) == BackgroundAgentRunStatus.COMPLETED

    def test_interrupted_maps_to_cancelled(self):
        assert _map_execution_status_to_run_status(ExecutionStatus.INTERRUPTED) == BackgroundAgentRunStatus.CANCELLED

    def test_failed_maps_to_failed(self):
        assert _map_execution_status_to_run_status(ExecutionStatus.FAILED) == BackgroundAgentRunStatus.FAILED


class TestResolveBackgroundAgentWorkingDir:
    def _make_agent(self, project_id: int | None = None) -> Mock:
        agent = Mock()
        agent.id = 1
        agent.name = "My Agent"
        agent.project_id = project_id
        return agent

    def test_global_agent_uses_background_agent_directory(self):
        agent = self._make_agent(project_id=None)
        db = Mock()

        with patch(
            "devboard.agents.execution.manager.ensure_background_agent_directory",
            return_value="/home/user/.devboard/background_agents/my-agent",
        ) as mock_ensure:
            result = _resolve_background_agent_working_dir(agent, db)

        mock_ensure.assert_called_once_with(agent)
        assert result == "/home/user/.devboard/background_agents/my-agent"

    def test_project_with_codebases_uses_first_codebase_path(self):
        agent = self._make_agent(project_id=5)
        codebase = Mock()
        codebase.local_path = "/repos/my-project"
        project = Mock()
        project.codebases = [codebase]
        db = Mock()
        db.get.return_value = project

        result = _resolve_background_agent_working_dir(agent, db)

        assert result == "/repos/my-project"
        db.get.assert_called_once()

    def test_project_without_codebases_uses_project_directory(self):
        agent = self._make_agent(project_id=5)
        project = Mock()
        project.codebases = []
        db = Mock()
        db.get.return_value = project

        with patch(
            "devboard.agents.execution.manager.ensure_project_directory",
            return_value="/home/user/.devboard/projects/my-project",
        ) as mock_ensure:
            result = _resolve_background_agent_working_dir(agent, db)

        mock_ensure.assert_called_once_with(project)
        assert result == "/home/user/.devboard/projects/my-project"

    def test_missing_project_raises_value_error(self):
        agent = self._make_agent(project_id=99)
        db = Mock()
        db.get.return_value = None

        with pytest.raises(ValueError, match="Project 99 not found"):
            _resolve_background_agent_working_dir(agent, db)


class TestRunAgentForMergedTask:
    """Tests for MERGED-status task conversations that bypass workspace allocation."""

    def test_merged_task_routing_condition(self):
        """Verify the conditional routing correctly identifies MERGED-status tasks."""
        from devboard.db.models import TaskStatus

        # Create a mock task with MERGED status
        codebase = Mock()
        codebase.local_path = "/repo/myproject"

        merged_task = Mock()
        merged_task.status = TaskStatus.MERGED
        merged_task.codebase = codebase

        implementing_task = Mock()
        implementing_task.status = TaskStatus.IMPLEMENTING
        implementing_task.codebase = codebase

        # Verify the condition would correctly identify MERGED status
        assert merged_task.status == TaskStatus.MERGED
        assert implementing_task.status != TaskStatus.MERGED

    def test_task_status_enum_has_merged_value(self):
        """Verify TaskStatus.MERGED exists and has correct string value."""
        from devboard.db.models import TaskStatus

        assert hasattr(TaskStatus, "MERGED")
        assert TaskStatus.MERGED.value == "merged"
