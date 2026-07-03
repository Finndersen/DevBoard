"""Tests for CodexAgent using the openai-codex SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai_codex.generated.v2_all import (
    AgentMessageThreadItem,
    CommandExecutionStatus,
    CommandExecutionThreadItem,
    ItemCompletedNotification,
    ThreadItem,
    ThreadTokenUsage,
    ThreadTokenUsageUpdatedNotification,
    Turn,
    TurnCompletedNotification,
    TurnStatus,
)
from openai_codex.models import Notification, UnknownNotification

from devboard.agents.engines.codex.agent import CodexAgent
from devboard.agents.events import (
    ContextUsage,
    LocalCommand,
    MessageRole,
    TextMessage,
)
from devboard.agents.language_models import LLMProvider
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.models.language_model import LanguageModelDB


def _make_model(provider: LLMProvider = LLMProvider.OPENAI, name: str = "gpt-5") -> LanguageModelDB:
    model = MagicMock(spec=LanguageModelDB)
    model.provider = provider
    model.name = name
    return model


def _make_role() -> MagicMock:
    role = MagicMock()
    role.get_system_prompt.return_value = "You are a helpful assistant."
    role.get_tools.return_value = []
    return role


def _notification(method: str, payload: object) -> Notification:
    return Notification(method=method, payload=payload)  # type: ignore[arg-type]


def _item_completed_notification(item_root: object) -> Notification:
    payload = ItemCompletedNotification(
        item=ThreadItem(root=item_root),  # type: ignore[arg-type]
        thread_id="t1",
        turn_id="turn1",
        completed_at_ms=0,
    )
    return _notification("item/completed", payload)


def _turn_completed_notification() -> Notification:
    turn = Turn(id="turn1", items=[], status=TurnStatus.completed)
    payload = TurnCompletedNotification(thread_id="t1", turn=turn)
    return _notification("turn/completed", payload)


def _token_usage_notification(input_tokens: int, output_tokens: int, cached: int) -> Notification:
    mock_breakdown = MagicMock()
    mock_breakdown.input_tokens = input_tokens
    mock_breakdown.output_tokens = output_tokens
    mock_breakdown.cached_input_tokens = cached
    mock_usage = MagicMock(spec=ThreadTokenUsage)
    mock_usage.last = mock_breakdown
    payload = ThreadTokenUsageUpdatedNotification(token_usage=mock_usage, thread_id="t1", turn_id="turn1")
    return _notification("thread/tokenUsage/updated", payload)


def _mock_codex_context(notifications: list[Notification], thread_id: str = "thread_new") -> MagicMock:
    """Build a mock AsyncCodex context manager that streams the given notifications."""
    mock_thread = MagicMock()
    mock_thread.id = thread_id

    async def mock_turn_stream() -> AsyncIterator[Notification]:
        for n in notifications:
            yield n

    mock_turn_handle = MagicMock()
    mock_turn_handle.stream = mock_turn_stream
    mock_turn_handle.run = AsyncMock()

    mock_thread.turn = AsyncMock(return_value=mock_turn_handle)
    mock_thread.run = AsyncMock()

    mock_codex = AsyncMock()
    mock_codex.__aenter__ = AsyncMock(return_value=mock_codex)
    mock_codex.__aexit__ = AsyncMock(return_value=None)
    mock_codex.thread_start = AsyncMock(return_value=mock_thread)
    mock_codex.thread_resume = AsyncMock(return_value=mock_thread)
    return mock_codex


@pytest.fixture
def agent() -> CodexAgent:
    return CodexAgent(role=_make_role(), model=_make_model())


class TestCodexAgentInit:
    def test_accepts_openai_model(self):
        agent = CodexAgent(role=_make_role(), model=_make_model(LLMProvider.OPENAI))
        assert agent.model is not None

    def test_rejects_non_openai_model(self):
        with pytest.raises(ValueError, match="Unsupported model provider"):
            CodexAgent(role=_make_role(), model=_make_model(LLMProvider.ANTHROPIC))

    def test_accepts_none_model(self):
        agent = CodexAgent(role=_make_role(), model=None)
        assert agent.model is None

    def test_stores_thread_id_and_working_dir(self):
        agent = CodexAgent(
            role=_make_role(),
            model=None,
            thread_id="thread_abc",
            working_dir="/some/path",
        )
        assert agent.thread_id == "thread_abc"
        assert agent.working_dir == "/some/path"

    def test_get_context_usage_initially_none(self, agent: CodexAgent):
        assert agent.get_context_usage() is None


class TestStreamEvents:
    @pytest.mark.asyncio
    async def test_rejects_tool_approvals(self, agent: CodexAgent):
        approvals = MagicMock(spec=ToolApprovals)
        with pytest.raises(ValueError, match="does not support tool approvals"):
            async for _ in agent.stream_events(approvals):
                pass

    @pytest.mark.asyncio
    async def test_yields_text_message_from_agent_message_item(self):
        item = AgentMessageThreadItem(id="msg_1", type="agentMessage", text="Done!")
        notifications = [_item_completed_notification(item), _turn_completed_notification()]
        mock_codex = _mock_codex_context(notifications)

        agent = CodexAgent(role=_make_role(), model=None)
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            collected = [event async for event in agent.stream_events("Do something")]

        assert len(collected) == 1
        msg = collected[0]
        assert isinstance(msg, TextMessage)
        assert msg.role == MessageRole.AGENT
        assert msg.text_content == "Done!"

    @pytest.mark.asyncio
    async def test_thread_id_set_from_thread_start(self):
        item = AgentMessageThreadItem(id="m1", type="agentMessage", text="Hi")
        notifications = [_item_completed_notification(item), _turn_completed_notification()]
        mock_codex = _mock_codex_context(notifications, thread_id="thread_xyz")

        agent = CodexAgent(role=_make_role(), model=None, thread_id=None)
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            async for _ in agent.stream_events("Hello"):
                pass

        assert agent.thread_id == "thread_xyz"

    @pytest.mark.asyncio
    async def test_uses_thread_resume_when_thread_id_set(self):
        item = AgentMessageThreadItem(id="m1", type="agentMessage", text="Resumed")
        notifications = [_item_completed_notification(item), _turn_completed_notification()]
        mock_codex = _mock_codex_context(notifications, thread_id="existing_thread")

        agent = CodexAgent(role=_make_role(), model=None, thread_id="existing_thread")
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            async for _ in agent.stream_events("Continue"):
                pass

        mock_codex.thread_resume.assert_called_once()
        mock_codex.thread_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_thread_start_when_no_thread_id(self):
        item = AgentMessageThreadItem(id="m1", type="agentMessage", text="New")
        notifications = [_item_completed_notification(item), _turn_completed_notification()]
        mock_codex = _mock_codex_context(notifications)

        agent = CodexAgent(role=_make_role(), model=None, thread_id=None)
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            async for _ in agent.stream_events("Start"):
                pass

        mock_codex.thread_start.assert_called_once()
        mock_codex.thread_resume.assert_not_called()

    @pytest.mark.asyncio
    async def test_stores_context_usage_from_token_usage_notification(self):
        item = AgentMessageThreadItem(id="m1", type="agentMessage", text="OK")
        notifications = [
            _item_completed_notification(item),
            _token_usage_notification(input_tokens=100, output_tokens=40, cached=30),
            _turn_completed_notification(),
        ]
        mock_codex = _mock_codex_context(notifications)

        agent = CodexAgent(role=_make_role(), model=None)
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            async for _ in agent.stream_events("Prompt"):
                pass

        usage = agent.get_context_usage()
        assert usage is not None
        assert isinstance(usage, ContextUsage)
        assert usage.input_tokens == 100
        assert usage.cache_read_tokens == 30
        assert usage.output_tokens == 40
        assert usage.cache_write_tokens == 0

    @pytest.mark.asyncio
    async def test_yields_multiple_event_types(self):
        cmd_item = CommandExecutionThreadItem(
            id="cmd_1",
            type="commandExecution",
            command="echo hi",
            aggregated_output="hi",
            exit_code=0,
            status=CommandExecutionStatus.completed,
            command_actions=[],
            cwd="/tmp",
        )
        msg_item = AgentMessageThreadItem(id="msg_1", type="agentMessage", text="Command ran successfully")
        notifications = [
            _item_completed_notification(cmd_item),
            _item_completed_notification(msg_item),
            _turn_completed_notification(),
        ]
        mock_codex = _mock_codex_context(notifications)

        agent = CodexAgent(role=_make_role(), model=None)
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            collected = [event async for event in agent.stream_events("Run command")]

        assert len(collected) == 2
        assert isinstance(collected[0], LocalCommand)
        assert isinstance(collected[1], TextMessage)

    @pytest.mark.asyncio
    async def test_passes_model_name_to_thread_start(self):
        item = AgentMessageThreadItem(id="m1", type="agentMessage", text="OK")
        notifications = [_item_completed_notification(item), _turn_completed_notification()]
        mock_codex = _mock_codex_context(notifications)

        agent = CodexAgent(role=_make_role(), model=_make_model(name="gpt-5"))
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            async for _ in agent.stream_events("Test"):
                pass

        call_kwargs = mock_codex.thread_start.call_args.kwargs
        assert call_kwargs["model"] == "gpt-5"

    @pytest.mark.asyncio
    async def test_config_overrides_passed_to_codex_config(self):
        item = AgentMessageThreadItem(id="m1", type="agentMessage", text="OK")
        notifications = [_item_completed_notification(item), _turn_completed_notification()]
        mock_codex = _mock_codex_context(notifications)

        overrides = ("mcp_servers.foo.type=http", 'mcp_servers.foo.url="http://127.0.0.1:9000/"')
        agent = CodexAgent(role=_make_role(), model=None, config_overrides=overrides)

        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex) as mock_cls:
            async for _ in agent.stream_events("Test"):
                pass

        codex_config = mock_cls.call_args.kwargs["config"]
        assert codex_config.config_overrides == overrides

    @pytest.mark.asyncio
    async def test_unknown_notifications_are_skipped(self):
        item = AgentMessageThreadItem(id="m1", type="agentMessage", text="Done")
        notifications = [
            _notification("some/unknown/event", UnknownNotification(params={})),
            _item_completed_notification(item),
            _turn_completed_notification(),
        ]
        mock_codex = _mock_codex_context(notifications)

        agent = CodexAgent(role=_make_role(), model=None)
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            collected = [event async for event in agent.stream_events("Prompt")]

        assert len(collected) == 1
        assert isinstance(collected[0], TextMessage)


class TestRun:
    @pytest.mark.asyncio
    async def test_run_returns_text_message(self):
        mock_result = MagicMock()
        mock_result.final_response = "Task done."
        mock_result.usage = None

        mock_thread = MagicMock()
        mock_thread.id = "thread_run_1"
        mock_thread.run = AsyncMock(return_value=mock_result)

        mock_codex = AsyncMock()
        mock_codex.__aenter__ = AsyncMock(return_value=mock_codex)
        mock_codex.__aexit__ = AsyncMock(return_value=None)
        mock_codex.thread_start = AsyncMock(return_value=mock_thread)
        mock_codex.thread_resume = AsyncMock(return_value=mock_thread)

        agent = CodexAgent(role=_make_role(), model=None)
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            result = await agent.run("Do the task")

        assert isinstance(result, TextMessage)
        assert result.role == MessageRole.AGENT
        assert result.text_content == "Task done."

    @pytest.mark.asyncio
    async def test_run_handles_none_final_response(self):
        mock_result = MagicMock()
        mock_result.final_response = None
        mock_result.usage = None

        mock_thread = MagicMock()
        mock_thread.id = "t1"
        mock_thread.run = AsyncMock(return_value=mock_result)

        mock_codex = AsyncMock()
        mock_codex.__aenter__ = AsyncMock(return_value=mock_codex)
        mock_codex.__aexit__ = AsyncMock(return_value=None)
        mock_codex.thread_start = AsyncMock(return_value=mock_thread)
        mock_codex.thread_resume = AsyncMock(return_value=mock_thread)

        agent = CodexAgent(role=_make_role(), model=None)
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            result = await agent.run("Prompt")

        assert isinstance(result, TextMessage)
        assert result.text_content == ""

    @pytest.mark.asyncio
    async def test_run_stores_usage(self):
        mock_breakdown = MagicMock()
        mock_breakdown.input_tokens = 50
        mock_breakdown.output_tokens = 20
        mock_breakdown.cached_input_tokens = 10
        mock_usage = MagicMock()
        mock_usage.last = mock_breakdown

        mock_result = MagicMock()
        mock_result.final_response = "Done"
        mock_result.usage = mock_usage

        mock_thread = MagicMock()
        mock_thread.id = "t1"
        mock_thread.run = AsyncMock(return_value=mock_result)

        mock_codex = AsyncMock()
        mock_codex.__aenter__ = AsyncMock(return_value=mock_codex)
        mock_codex.__aexit__ = AsyncMock(return_value=None)
        mock_codex.thread_start = AsyncMock(return_value=mock_thread)
        mock_codex.thread_resume = AsyncMock(return_value=mock_thread)

        agent = CodexAgent(role=_make_role(), model=None)
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            await agent.run("Run")

        usage = agent.get_context_usage()
        assert usage is not None
        assert usage.input_tokens == 50
        assert usage.cache_read_tokens == 10
        assert usage.output_tokens == 20

    @pytest.mark.asyncio
    async def test_run_uses_thread_resume_when_thread_id_set(self):
        mock_result = MagicMock()
        mock_result.final_response = "Resumed"
        mock_result.usage = None

        mock_thread = MagicMock()
        mock_thread.id = "existing"
        mock_thread.run = AsyncMock(return_value=mock_result)

        mock_codex = AsyncMock()
        mock_codex.__aenter__ = AsyncMock(return_value=mock_codex)
        mock_codex.__aexit__ = AsyncMock(return_value=None)
        mock_codex.thread_start = AsyncMock(return_value=mock_thread)
        mock_codex.thread_resume = AsyncMock(return_value=mock_thread)

        agent = CodexAgent(role=_make_role(), model=None, thread_id="existing")
        with patch("devboard.agents.engines.codex.agent.AsyncCodex", return_value=mock_codex):
            await agent.run("Continue")

        mock_codex.thread_resume.assert_called_once()
        mock_codex.thread_start.assert_not_called()
