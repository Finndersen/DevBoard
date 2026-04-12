"""Tests for _run_agent_for_conversation background execution coroutine."""

import asyncio
import datetime
from contextlib import ExitStack, asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.events import ConversationEvent, MessageRole, TextMessage
from devboard.api.dependencies.services import ExecutionServices
from devboard.db.models import Conversation, Project, Task
from devboard.db.models.task import TaskStatus


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
    exec_service.last_usage = None  # must be None or ContextUsage for ExecutionCompleteEvent validation
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
            mock_db.info = {}
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
            additional_write_dirs=None,
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

            mock_db.info = {}
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

        # Queue now contains: AgentRunStartedEvent, the agent event, AgentRunCompletedEvent
        items = []
        while not broadcast_queue.empty():
            items.append(broadcast_queue.get_nowait())
        agent_events = [(cid, e) for cid, e in items if isinstance(e, TextMessage)]
        assert len(agent_events) == 1
        conv_id, queued = agent_events[0]
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

            mock_db.info = {}
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

        # commit is called twice: once for update_last_activity (start-of-run) and
        # once in the finally block for the agent_run.completed log
        assert mock_db.commit.call_count == 2
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

            mock_db.info = {}
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

        # commit is called twice: once for update_last_activity (start-of-run) and
        # once in the finally block
        assert mock_db.commit.call_count == 2
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


def _make_task_conversation(slot_path: str, codebase_local_path: str):
    """Return (conversation, task, allocation) mocks for a task conversation."""
    codebase = Mock()
    codebase.local_path = codebase_local_path

    task = Mock(spec=Task)
    task.id = 42
    task.status = TaskStatus.IMPLEMENTING
    task.codebase = codebase

    conversation = Mock(spec=Conversation)
    conversation.id = 1
    conversation.get_parent_entity.return_value = task

    slot = Mock()
    slot.id = 10
    slot.path = slot_path

    allocation = Mock()
    allocation.reused = True
    allocation.slot = slot

    return conversation, task, allocation


async def _empty_async_gen():
    return
    yield  # noqa: unreachable


class TestTaskConversationWriteDirs:
    """Tests that additional_write_dirs is correctly computed for task conversations."""

    def _setup_task_workspace(self, mock_services, allocation):
        """Configure mock workspace service and return patch list for task conversation tests."""

        @asynccontextmanager
        async def mock_allocate(_task):
            yield allocation

        mock_workspace = Mock()
        mock_workspace.allocate_workspace = mock_allocate
        mock_workspace.prepare_workspace.return_value = _empty_async_gen()
        mock_services.workspace_service = mock_workspace

        mock_resolver = AsyncMock()
        mock_resolver.__aenter__ = AsyncMock(return_value=mock_resolver)
        mock_resolver.__aexit__ = AsyncMock(return_value=None)
        mock_resolver.run = AsyncMock(return_value=mock_services)

        mock_db = Mock()
        mock_db.info = {}
        return [
            patch("devboard.agents.execution.manager.SessionLocal", return_value=mock_db),
            patch("devboard.agents.execution.manager.DependencyResolver", return_value=mock_resolver),
            patch(
                "devboard.agents.execution.manager.create_agent_role_for_conversation",
                new_callable=AsyncMock,
            ),
            patch("devboard.agents.execution.manager.ensure_project_directory", return_value="/projects/test"),
            patch("devboard.agents.execution.manager._drain_events", new_callable=AsyncMock),
        ]

    @pytest.mark.asyncio
    async def test_worktree_path_adds_codebase_to_write_dirs(self, mock_services):
        """When slot path differs from codebase local_path, codebase path is in additional_write_dirs."""
        codebase_path = "/repos/myapp"
        worktree_path = "/repos/myapp/.git/worktrees/task-42"
        conversation, _task, allocation = _make_task_conversation(worktree_path, codebase_path)
        mock_services.conversation_repo.get_by_id.return_value = conversation

        exec_service = _make_mock_exec_service(_empty_async_gen)
        mock_create_exec = Mock(return_value=exec_service)
        patches = self._setup_task_workspace(mock_services, allocation)

        with (
            ExitStack() as stack,
            patch("devboard.agents.execution.manager.create_agent_execution_service", mock_create_exec),
        ):
            for p in patches:
                stack.enter_context(p)

            from devboard.agents.execution.manager import _run_agent_for_conversation

            await _run_agent_for_conversation(
                asyncio.Queue(), asyncio.Event(), conversation_id=1, message_or_approvals="Hello"
            )

        mock_create_exec.assert_called_once_with(
            conversation=conversation,
            role=mock_create_exec.call_args.kwargs["role"],
            conversation_repo=mock_services.conversation_repo,
            agent_config_service=mock_services.agent_config_service,
            working_dir=worktree_path,
            interrupt_event=mock_create_exec.call_args.kwargs["interrupt_event"],
            additional_write_dirs=[codebase_path],
        )

    @pytest.mark.asyncio
    async def test_same_path_does_not_add_write_dirs(self, mock_services):
        """When slot path equals codebase local_path, additional_write_dirs is None."""
        codebase_path = "/repos/myapp"
        conversation, _task, allocation = _make_task_conversation(codebase_path, codebase_path)
        mock_services.conversation_repo.get_by_id.return_value = conversation

        exec_service = _make_mock_exec_service(_empty_async_gen)
        mock_create_exec = Mock(return_value=exec_service)
        patches = self._setup_task_workspace(mock_services, allocation)

        with (
            ExitStack() as stack,
            patch("devboard.agents.execution.manager.create_agent_execution_service", mock_create_exec),
        ):
            for p in patches:
                stack.enter_context(p)

            from devboard.agents.execution.manager import _run_agent_for_conversation

            await _run_agent_for_conversation(
                asyncio.Queue(), asyncio.Event(), conversation_id=1, message_or_approvals="Hello"
            )

        mock_create_exec.assert_called_once_with(
            conversation=conversation,
            role=mock_create_exec.call_args.kwargs["role"],
            conversation_repo=mock_services.conversation_repo,
            agent_config_service=mock_services.agent_config_service,
            working_dir=codebase_path,
            interrupt_event=mock_create_exec.call_args.kwargs["interrupt_event"],
            additional_write_dirs=None,
        )
