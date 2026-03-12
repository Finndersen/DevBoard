"""Tests for run_agent_for_conversation background execution coroutine."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.events import ConversationEvent, MessageRole, TextMessage
from devboard.api.dependencies.services import ExecutionServices
from devboard.db.models import Conversation


@pytest.fixture
def mock_services() -> Mock:
    """Create mock ExecutionServices with all required attributes."""
    services = Mock(spec=ExecutionServices)
    services.conversation_repo = Mock()
    services.document_repo = Mock()
    services.agent_config_service = Mock()
    services.integration_service = Mock()
    services.task_service = Mock()
    services.task_git_service = Mock()
    services.workspace_allocation_service = Mock()
    return services


@pytest.fixture
def mock_conversation() -> Mock:
    """Create a mock Conversation."""
    conversation = Mock(spec=Conversation)
    conversation.id = 1
    conversation.get_parent_entity.return_value = Mock()  # non-Task parent
    return conversation


class TestRunAgentForConversation:
    """Tests for the run_agent_for_conversation coroutine."""

    @pytest.mark.asyncio
    async def test_passes_conversation_repo_to_create_role(self, mock_services, mock_conversation):
        """Verify conversation_repo is passed to create_agent_role_for_conversation."""
        mock_role = Mock()
        mock_execution_service = Mock()

        async def mock_stream():
            return
            yield  # make it an async generator

        mock_execution_service.stream_events_for_message_or_approval.return_value = mock_stream()

        with (
            patch("devboard.agents.background_execution.SessionLocal") as mock_session_local,
            patch("devboard.agents.background_execution.DependencyResolver") as mock_resolver_cls,
            patch(
                "devboard.agents.background_execution.create_agent_role_for_conversation", new_callable=AsyncMock
            ) as mock_create_role,
            patch("devboard.agents.background_execution.create_agent_execution_service") as mock_create_exec,
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
            mock_create_exec.return_value = mock_execution_service

            event_queue: asyncio.Queue[ConversationEvent | None] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.background_execution import run_agent_for_conversation

            await run_agent_for_conversation(
                event_queue,
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
            task_git_service=mock_services.task_git_service,
            conversation_repo=mock_services.conversation_repo,
        )

    @pytest.mark.asyncio
    async def test_events_pushed_to_queue(self, mock_services, mock_conversation):
        """Verify events from the agent stream are pushed to the event queue."""
        import datetime

        mock_role = Mock()
        mock_execution_service = Mock()
        event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Hello",
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        async def mock_stream():
            yield event

        mock_execution_service.stream_events_for_message_or_approval.return_value = mock_stream()

        with (
            patch("devboard.agents.background_execution.SessionLocal") as mock_session_local,
            patch("devboard.agents.background_execution.DependencyResolver") as mock_resolver_cls,
            patch(
                "devboard.agents.background_execution.create_agent_role_for_conversation", new_callable=AsyncMock
            ) as mock_create_role,
            patch("devboard.agents.background_execution.create_agent_execution_service") as mock_create_exec,
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
            mock_create_exec.return_value = mock_execution_service

            event_queue: asyncio.Queue[ConversationEvent | None] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.background_execution import run_agent_for_conversation

            await run_agent_for_conversation(
                event_queue,
                interrupt_event,
                conversation_id=1,
                message_or_approvals="Hello",
            )

        assert event_queue.qsize() == 1
        queued = event_queue.get_nowait()
        assert queued == event

    @pytest.mark.asyncio
    async def test_db_committed_on_success(self, mock_services, mock_conversation):
        """Verify db.commit() is called after successful execution."""
        mock_role = Mock()
        mock_execution_service = Mock()

        async def mock_stream():
            return
            yield

        mock_execution_service.stream_events_for_message_or_approval.return_value = mock_stream()

        with (
            patch("devboard.agents.background_execution.SessionLocal") as mock_session_local,
            patch("devboard.agents.background_execution.DependencyResolver") as mock_resolver_cls,
            patch(
                "devboard.agents.background_execution.create_agent_role_for_conversation", new_callable=AsyncMock
            ) as mock_create_role,
            patch("devboard.agents.background_execution.create_agent_execution_service") as mock_create_exec,
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
            mock_create_exec.return_value = mock_execution_service

            event_queue: asyncio.Queue[ConversationEvent | None] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.background_execution import run_agent_for_conversation

            await run_agent_for_conversation(
                event_queue,
                interrupt_event,
                conversation_id=1,
                message_or_approvals="Hello",
            )

        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_rolled_back_on_exception(self, mock_services, mock_conversation):
        """Verify db.rollback() is called when the agent stream raises an exception."""
        mock_role = Mock()
        mock_execution_service = Mock()

        async def mock_stream():
            raise RuntimeError("Agent failed")
            yield  # make it an async generator

        mock_execution_service.stream_events_for_message_or_approval.return_value = mock_stream()

        with (
            patch("devboard.agents.background_execution.SessionLocal") as mock_session_local,
            patch("devboard.agents.background_execution.DependencyResolver") as mock_resolver_cls,
            patch(
                "devboard.agents.background_execution.create_agent_role_for_conversation", new_callable=AsyncMock
            ) as mock_create_role,
            patch("devboard.agents.background_execution.create_agent_execution_service") as mock_create_exec,
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
            mock_create_exec.return_value = mock_execution_service

            event_queue: asyncio.Queue[ConversationEvent | None] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.background_execution import run_agent_for_conversation

            with pytest.raises(RuntimeError, match="Agent failed"):
                await run_agent_for_conversation(
                    event_queue,
                    interrupt_event,
                    conversation_id=1,
                    message_or_approvals="Hello",
                )

        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_not_found_raises(self, mock_services):
        """Verify ValueError is raised when conversation is not found."""
        with (
            patch("devboard.agents.background_execution.SessionLocal") as mock_session_local,
            patch("devboard.agents.background_execution.DependencyResolver") as mock_resolver_cls,
        ):
            mock_db = Mock()
            mock_session_local.return_value = mock_db

            mock_resolver = AsyncMock()
            mock_resolver.__aenter__ = AsyncMock(return_value=mock_resolver)
            mock_resolver.__aexit__ = AsyncMock(return_value=None)
            mock_resolver.run = AsyncMock(return_value=mock_services)
            mock_resolver_cls.return_value = mock_resolver

            mock_services.conversation_repo.get_by_id.return_value = None

            event_queue: asyncio.Queue[ConversationEvent | None] = asyncio.Queue()
            interrupt_event = asyncio.Event()

            from devboard.agents.background_execution import run_agent_for_conversation

            with pytest.raises(ValueError, match="Conversation 99 not found"):
                await run_agent_for_conversation(
                    event_queue,
                    interrupt_event,
                    conversation_id=99,
                    message_or_approvals="Hello",
                )
