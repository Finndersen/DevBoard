"""Tests for ConversationExecutionManager and related helpers."""

import asyncio
import datetime
from unittest.mock import Mock, patch

import pytest

from devboard.agents.events import AgentRunCompletedEvent, AgentRunStartedEvent, MessageRole, TextMessage
from devboard.agents.exceptions import AgentInterruptedError
from devboard.agents.execution.manager import ConversationExecutionManager
from devboard.agents.execution.types import ConversationExecution, ExecutionStatus


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

        assert manager._executions[42] is stale_exec

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
