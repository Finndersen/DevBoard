"""Tests for _run_agent_for_conversation background execution coroutine."""

import asyncio
import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.events import ConversationEvent, MessageRole, TextMessage
from devboard.api.dependencies.services import ExecutionServices
from devboard.db.models import Conversation, Project


@pytest.fixture
def mock_services() -> Mock:
    """Create mock ExecutionServices with all required attributes."""
    services = Mock(spec=ExecutionServices)
    services.conversation_repo = Mock()
    services.document_repo = Mock()
    services.agent_config_service = Mock()
    services.integration_service = Mock()
    services.task_service = Mock()
    services.workspace_service = Mock()
    return services


@pytest.fixture
def mock_conversation() -> Mock:
    """Create a mock Conversation with a Project parent."""
    conversation = Mock(spec=Conversation)
    conversation.id = 1
    project = Mock(spec=Project)
    conversation.get_parent_entity.return_value = project
    return conversation


def _make_mock_exec_service(stream_fn):
    """Create a mock execution service whose stream_events_for_message_or_approval returns the given async generator."""
    exec_service = Mock()
    exec_service.stream_events_for_message_or_approval.return_value = stream_fn()
    return exec_service


class TestRunAgentForConversation:
    """Tests for the _run_agent_for_conversation coroutine."""

    @pytest.mark.asyncio
    async def test_passes_services_to_factories(self, mock_services, mock_conversation):
        """Verify services are passed to role and execution service factories."""

        async def empty_stream():
            return
            yield  # make it an async generator

        mock_role = Mock()

        with (
            patch("devboard.agents.execution.manager.SessionLocal") as mock_session_local,
            patch("devboard.agents.execution.manager.DependencyResolver") as mock_resolver_cls,
            patch(
                "devboard.agents.execution.manager.create_agent_role_for_conversation", new_callable=AsyncMock
            ) as mock_create_role,
            patch("devboard.agents.execution.manager.create_agent_execution_service") as mock_create_exec,
            patch("devboard.agents.execution.manager.ensure_project_directory", return_value="/projects/test"),
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            mock_resolver = AsyncMock()
            mock_resolver.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_resolver.__aexit__ = AsyncMock(return_value=None)
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_resolver_cls.return_value = mock_resolver

            mock_services.conversation_repo.get_by_id.return_value = mock_conversation
            mock_create_role.return_value = mock_role
            mock_create_exec.return_value = _make_mock_exec_service(empty_stream)

            broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.execution.manager import _run_agent_for_conversation

            await _run_agent_for_conversation(
                broadcast_queue,
                interrupt_event,
                conversation_id=1,
                message_or_approvals="Hello",
            )

        mock_create_role.assert_called_once_with(
            conversation=mock_conversation,
            document_repo=mock_services.document_repo,
            agent_config_service=mock_services.agent_config_service,
            integration_service=mock_services.integration_service,
            task_service=mock_services.task_service,
            conversation_repo=mock_services.conversation_repo,
            working_dir="/projects/test",
        )
        mock_create_exec.assert_called_once_with(
            conversation=mock_conversation,
            role=mock_role,
            conversation_repo=mock_services.conversation_repo,
            agent_config_service=mock_services.agent_config_service,
            working_dir="/projects/test",
            interrupt_event=interrupt_event,
        )

    @pytest.mark.asyncio
    async def test_events_pushed_to_broadcast_queue(self, mock_services, mock_conversation):
        """Verify events from the agent stream are pushed to the broadcast queue with conversation_id."""
        event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Hello",
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        async def mock_stream():
            yield event

        with (
            patch("devboard.agents.execution.manager.SessionLocal") as mock_session_local,
            patch("devboard.agents.execution.manager.DependencyResolver") as mock_resolver_cls,
            patch("devboard.agents.execution.manager.create_agent_role_for_conversation", new_callable=AsyncMock),
            patch("devboard.agents.execution.manager.create_agent_execution_service") as mock_create_exec,
            patch("devboard.agents.execution.manager.ensure_project_directory", return_value="/projects/test"),
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            mock_resolver = AsyncMock()
            mock_resolver.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_resolver.__aexit__ = AsyncMock(return_value=None)
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_resolver_cls.return_value = mock_resolver

            mock_services.conversation_repo.get_by_id.return_value = mock_conversation
            mock_create_exec.return_value = _make_mock_exec_service(mock_stream)

            broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.execution.manager import _run_agent_for_conversation

            await _run_agent_for_conversation(
                broadcast_queue,
                interrupt_event,
                conversation_id=1,
                message_or_approvals="Hello",
            )

        assert broadcast_queue.qsize() == 1
        conv_id, queued = broadcast_queue.get_nowait()
        assert conv_id == 1
        assert queued == event

    @pytest.mark.asyncio
    async def test_db_committed_on_success(self, mock_services, mock_conversation):
        """Verify db.commit() is called after successful execution."""

        async def empty_stream():
            return
            yield

        with (
            patch("devboard.agents.execution.manager.SessionLocal") as mock_session_local,
            patch("devboard.agents.execution.manager.DependencyResolver") as mock_resolver_cls,
            patch("devboard.agents.execution.manager.create_agent_role_for_conversation", new_callable=AsyncMock),
            patch("devboard.agents.execution.manager.create_agent_execution_service") as mock_create_exec,
            patch("devboard.agents.execution.manager.ensure_project_directory", return_value="/projects/test"),
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            mock_resolver = AsyncMock()
            mock_resolver.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_resolver.__aexit__ = AsyncMock(return_value=None)
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_resolver_cls.return_value = mock_resolver

            mock_services.conversation_repo.get_by_id.return_value = mock_conversation
            mock_create_exec.return_value = _make_mock_exec_service(empty_stream)

            broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.execution.manager import _run_agent_for_conversation

            await _run_agent_for_conversation(
                broadcast_queue,
                interrupt_event,
                conversation_id=1,
                message_or_approvals="Hello",
            )

        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_committed_on_exception(self, mock_services, mock_conversation):
        """Verify db.commit() is called on exception to preserve partial progress."""

        async def failing_stream():
            raise RuntimeError("Agent failed")
            yield  # make it an async generator

        with (
            patch("devboard.agents.execution.manager.SessionLocal") as mock_session_local,
            patch("devboard.agents.execution.manager.DependencyResolver") as mock_resolver_cls,
            patch("devboard.agents.execution.manager.create_agent_role_for_conversation", new_callable=AsyncMock),
            patch("devboard.agents.execution.manager.create_agent_execution_service") as mock_create_exec,
            patch("devboard.agents.execution.manager.ensure_project_directory", return_value="/projects/test"),
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            mock_resolver = AsyncMock()
            mock_resolver.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_resolver.__aexit__ = AsyncMock(return_value=None)
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_resolver_cls.return_value = mock_resolver

            mock_services.conversation_repo.get_by_id.return_value = mock_conversation
            mock_create_exec.return_value = _make_mock_exec_service(failing_stream)

            broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.execution.manager import _run_agent_for_conversation

            with pytest.raises(RuntimeError, match="Agent failed"):
                await _run_agent_for_conversation(
                    broadcast_queue,
                    interrupt_event,
                    conversation_id=1,
                    message_or_approvals="Hello",
                )

        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_not_found_raises(self, mock_services):
        """Verify ValueError is raised when conversation is not found."""
        with (
            patch("devboard.agents.execution.manager.SessionLocal") as mock_session_local,
            patch("devboard.agents.execution.manager.DependencyResolver") as mock_resolver_cls,
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            mock_resolver = AsyncMock()
            mock_resolver.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_resolver.__aexit__ = AsyncMock(return_value=None)
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_resolver_cls.return_value = mock_resolver

            mock_services.conversation_repo.get_by_id.return_value = None

            broadcast_queue: asyncio.Queue[tuple[int, ConversationEvent]] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.execution.manager import _run_agent_for_conversation

            with pytest.raises(ValueError, match="Conversation 99 not found"):
                await _run_agent_for_conversation(
                    broadcast_queue,
                    interrupt_event,
                    conversation_id=99,
                    message_or_approvals="Hello",
                )
