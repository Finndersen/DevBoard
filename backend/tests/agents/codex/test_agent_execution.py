"""Tests for CodexAgentExecutionService."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from devboard.agents.engines.codex.agent_execution import CodexAgentExecutionService
from devboard.agents.events import (
    ContextUsage,
    MessageRole,
    SystemEvent,
    SystemEventType,
    TextMessage,
)
from devboard.agents.exceptions import AgentInterruptedError


def _make_service(
    external_session_id: str | None = None,
) -> CodexAgentExecutionService:
    """Build a CodexAgentExecutionService with mocked dependencies."""
    conversation = Mock()
    conversation.id = 1
    conversation.external_session_id = external_session_id
    conversation.model_id = None
    conversation.agent_role = "task_implementation"

    role = Mock()
    role.get_context_content = AsyncMock(return_value="context content")
    role.get_system_prompt.return_value = "System prompt"
    role.get_tools.return_value = []
    role.get_custom_instructions.return_value = ""

    conversation_repo = Mock()
    # Replicate the real mutation so subsequent per-event checks see the updated value
    conversation_repo.update_external_session_id = Mock(
        side_effect=lambda conv, sid: setattr(conv, "external_session_id", sid)
    )
    conversation_repo.commit = Mock()

    history_service = Mock()

    agent_config_service = Mock()
    agent_config_service.get_enabled_mcp_tools.return_value = []
    agent_config_service.get_model_by_id = Mock(return_value=None)

    return CodexAgentExecutionService(
        conversation=conversation,
        role=role,
        conversation_repository=conversation_repo,
        history_service=history_service,
        agent_config_service=agent_config_service,
        working_dir="/test/workdir",
    )


def _make_mock_agent(
    thread_id: str | None = "thread_new",
    events: list | None = None,
    context_usage: ContextUsage | None = None,
) -> MagicMock:
    """Build a mock CodexAgent that streams given events and returns given usage."""
    agent = MagicMock()
    agent.thread_id = thread_id
    agent.get_context_usage = Mock(return_value=context_usage)

    async def _stream_events(message: object) -> AsyncIterator:
        for event in events or []:
            yield event

    agent.stream_events = _stream_events
    return agent


class TestThreadIdProperty:
    def test_returns_external_session_id(self):
        service = _make_service(external_session_id="thread_abc")
        assert service.thread_id == "thread_abc"

    def test_returns_none_when_no_session(self):
        service = _make_service(external_session_id=None)
        assert service.thread_id is None


class TestContextMessageInjection:
    @pytest.mark.asyncio
    async def test_builds_context_message_when_thread_id_is_none(self):
        """On first run (no thread_id), _enrich_message is called with is_first_message=True."""
        service = _make_service(external_session_id=None)
        mock_agent = _make_mock_agent(thread_id=None)

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
            patch.object(
                service,
                "_enrich_message",
                new=AsyncMock(return_value="[context] original message"),
            ) as mock_enrich,
        ):
            async for _ in service._stream_events_impl("original message", []):
                pass

        mock_enrich.assert_called_once_with("original message", is_first_message=True)

    @pytest.mark.asyncio
    async def test_does_not_build_context_when_thread_id_exists(self):
        """On subsequent runs (thread_id set), _enrich_message is called with is_first_message=False."""
        service = _make_service(external_session_id="existing_thread")
        mock_agent = _make_mock_agent(thread_id="existing_thread")

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
            patch.object(
                service,
                "_enrich_message",
                new=AsyncMock(return_value="follow-up message"),
            ) as mock_enrich,
        ):
            async for _ in service._stream_events_impl("follow-up message", []):
                pass

        mock_enrich.assert_called_once_with("follow-up message", is_first_message=False)


class TestExternalSessionIdUpdate:
    @pytest.mark.asyncio
    async def test_updates_session_id_when_thread_id_changes(self):
        """When agent.thread_id differs from conversation.external_session_id, the DB is updated."""
        service = _make_service(external_session_id=None)
        text_event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Hello",
            timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )
        mock_agent = _make_mock_agent(thread_id="brand_new_thread", events=[text_event])

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
            patch.object(service, "_enrich_message", new=AsyncMock(return_value="ctx + msg")),
        ):
            events = [e async for e in service._stream_events_impl("start", [])]

        service.conversation_repo.update_external_session_id.assert_called_once_with(
            service.conversation, "brand_new_thread"
        )
        service.conversation_repo.commit.assert_called_once()

        # A CONVERSATION_UPDATED system event must be in the output
        system_events = [e for e in events if isinstance(e, SystemEvent)]
        assert any(e.sub_type == SystemEventType.CONVERSATION_UPDATED for e in system_events)

    @pytest.mark.asyncio
    async def test_yields_conversation_updated_event_with_new_thread_id(self):
        """The CONVERSATION_UPDATED event must carry the new external_session_id."""
        service = _make_service(external_session_id=None)
        # At least one event must be yielded to trigger the thread_id check inside the loop
        dummy_event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Hi",
            timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )
        mock_agent = _make_mock_agent(thread_id="new_thread_xyz", events=[dummy_event])

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
            patch.object(service, "_enrich_message", new=AsyncMock(return_value="ctx")),
        ):
            events = [e async for e in service._stream_events_impl("msg", [])]

        updated_events = [
            e for e in events if isinstance(e, SystemEvent) and e.sub_type == SystemEventType.CONVERSATION_UPDATED
        ]
        assert len(updated_events) == 1
        assert updated_events[0].data["updated_fields"]["external_session_id"] == "new_thread_xyz"
        assert updated_events[0].data["conversation_id"] == 1

    @pytest.mark.asyncio
    async def test_session_id_update_fires_exactly_once_for_multi_event_turn(self):
        """Even with multiple events, the DB update and CONVERSATION_UPDATED event occur only once."""
        service = _make_service(external_session_id=None)

        def _make_text(text: str) -> TextMessage:
            return TextMessage(
                role=MessageRole.AGENT,
                text_content=text,
                timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

        mock_agent = _make_mock_agent(
            thread_id="multi_event_thread",
            events=[_make_text("First"), _make_text("Second"), _make_text("Third")],
        )

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
            patch.object(service, "_enrich_message", new=AsyncMock(return_value="ctx")),
        ):
            events = [e async for e in service._stream_events_impl("start", [])]

        service.conversation_repo.update_external_session_id.assert_called_once()
        updated_events = [
            e for e in events if isinstance(e, SystemEvent) and e.sub_type == SystemEventType.CONVERSATION_UPDATED
        ]
        assert len(updated_events) == 1

    @pytest.mark.asyncio
    async def test_no_update_when_thread_id_unchanged(self):
        """When agent.thread_id matches conversation.external_session_id, no DB update occurs."""
        service = _make_service(external_session_id="stable_thread")
        mock_agent = _make_mock_agent(thread_id="stable_thread", events=[])

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
        ):
            events = [e async for e in service._stream_events_impl("continue", [])]

        service.conversation_repo.update_external_session_id.assert_not_called()
        service.conversation_repo.commit.assert_not_called()
        updated_events = [
            e for e in events if isinstance(e, SystemEvent) and e.sub_type == SystemEventType.CONVERSATION_UPDATED
        ]
        assert len(updated_events) == 0


class TestMCPHostLifecycle:
    @pytest.mark.asyncio
    async def test_mcp_host_stopped_after_streaming(self):
        """MCP host stop() is called after agent streaming completes."""
        service = _make_service(external_session_id="t1")
        mock_agent = _make_mock_agent(thread_id="t1", events=[])

        mock_host = AsyncMock()
        mock_host.stop = AsyncMock()

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(mock_host, ("override=1",)))),
        ):
            async for _ in service._stream_events_impl("msg", []):
                pass

        mock_host.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_host_stopped_even_on_exception(self):
        """MCP host stop() is called even when agent.stream_events raises."""
        service = _make_service(external_session_id="t1")

        agent = MagicMock()
        agent.thread_id = "t1"
        agent.get_context_usage = Mock(return_value=None)

        async def _failing_stream(message: object) -> AsyncIterator:
            raise RuntimeError("agent error")
            yield  # pragma: no cover

        agent.stream_events = _failing_stream

        mock_host = AsyncMock()
        mock_host.stop = AsyncMock()

        with (
            patch.object(service, "_get_agent", return_value=agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(mock_host, ()))),
        ):
            with pytest.raises(RuntimeError, match="agent error"):
                async for _ in service._stream_events_impl("msg", []):
                    pass

        mock_host.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_mcp_host_when_none_returned(self):
        """When _setup_mcp_host returns None, no stop() is attempted."""
        service = _make_service(external_session_id="t1")
        mock_agent = _make_mock_agent(thread_id="t1", events=[])

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
        ):
            # Should not raise
            async for _ in service._stream_events_impl("msg", []):
                pass


class TestContextUsagePropagation:
    @pytest.mark.asyncio
    async def test_yields_context_usage_after_events(self):
        """ContextUsage from agent.get_context_usage() is yielded after the event stream."""
        service = _make_service(external_session_id="t1")
        usage = ContextUsage(
            input_tokens=200,
            output_tokens=80,
            cache_read_tokens=50,
            cache_write_tokens=0,
            cost_usd=None,
        )
        text_event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Result",
            timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )
        mock_agent = _make_mock_agent(thread_id="t1", events=[text_event], context_usage=usage)

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
        ):
            events = [e async for e in service._stream_events_impl("msg", [])]

        usage_events = [e for e in events if isinstance(e, ContextUsage)]
        assert len(usage_events) == 1
        assert usage_events[0].input_tokens == 200
        assert usage_events[0].output_tokens == 80

        # ContextUsage should come after the TextMessage
        text_idx = next(i for i, e in enumerate(events) if isinstance(e, TextMessage))
        usage_idx = next(i for i, e in enumerate(events) if isinstance(e, ContextUsage))
        assert usage_idx > text_idx

    @pytest.mark.asyncio
    async def test_no_context_usage_yielded_when_agent_returns_none(self):
        """When agent.get_context_usage() returns None, no ContextUsage is yielded."""
        service = _make_service(external_session_id="t1")
        mock_agent = _make_mock_agent(thread_id="t1", events=[], context_usage=None)

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
        ):
            events = [e async for e in service._stream_events_impl("msg", [])]

        assert not any(isinstance(e, ContextUsage) for e in events)


class TestInterruptHandling:
    @pytest.mark.asyncio
    async def test_raises_agent_interrupted_error_when_interrupt_set(self):
        """When _interrupt_event is set after streaming, AgentInterruptedError is raised."""
        service = _make_service(external_session_id="t1")
        mock_agent = _make_mock_agent(thread_id="t1", events=[])

        interrupt_event = asyncio.Event()
        interrupt_event.set()
        service._interrupt_event = interrupt_event

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
        ):
            with pytest.raises(AgentInterruptedError):
                async for _ in service._stream_events_impl("msg", []):
                    pass

    @pytest.mark.asyncio
    async def test_no_interrupt_error_when_event_not_set(self):
        """When _interrupt_event is not set, no AgentInterruptedError is raised."""
        service = _make_service(external_session_id="t1")
        mock_agent = _make_mock_agent(thread_id="t1", events=[])

        interrupt_event = asyncio.Event()
        # Not set
        service._interrupt_event = interrupt_event

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
        ):
            # Should not raise
            async for _ in service._stream_events_impl("msg", []):
                pass


class TestRunImpl:
    @pytest.mark.asyncio
    async def test_builds_context_message_on_first_run(self):
        """_run_impl calls _enrich_message with is_first_message=True when thread_id is None."""
        service = _make_service(external_session_id=None)

        mock_agent = MagicMock()
        mock_agent.thread_id = "new_thread"
        mock_agent.run = AsyncMock(
            return_value=TextMessage(
                role=MessageRole.AGENT,
                text_content="Done",
                timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )
        )

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
            patch.object(
                service,
                "_enrich_message",
                new=AsyncMock(return_value="[ctx] original"),
            ) as mock_enrich,
        ):
            await service._run_impl("original", [])

        mock_enrich.assert_called_once_with("original", is_first_message=True)
        mock_agent.run.assert_called_once_with("[ctx] original")

    @pytest.mark.asyncio
    async def test_does_not_build_context_when_thread_id_exists(self):
        """_run_impl calls _enrich_message with is_first_message=False when thread_id is set."""
        service = _make_service(external_session_id="existing")

        mock_agent = MagicMock()
        mock_agent.thread_id = "existing"
        mock_agent.run = AsyncMock(
            return_value=TextMessage(
                role=MessageRole.AGENT,
                text_content="Done",
                timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )
        )

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
            patch.object(
                service,
                "_enrich_message",
                new=AsyncMock(return_value="follow-up"),
            ) as mock_enrich,
        ):
            await service._run_impl("follow-up", [])

        mock_enrich.assert_called_once_with("follow-up", is_first_message=False)
        mock_agent.run.assert_called_once_with("follow-up")

    @pytest.mark.asyncio
    async def test_updates_session_id_when_thread_changes(self):
        """_run_impl updates external_session_id when agent returns a new thread_id."""
        service = _make_service(external_session_id=None)

        mock_agent = MagicMock()
        mock_agent.thread_id = "brand_new"
        mock_agent.run = AsyncMock(
            return_value=TextMessage(
                role=MessageRole.AGENT,
                text_content="Done",
                timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )
        )

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(None, ()))),
            patch.object(service, "_enrich_message", new=AsyncMock(return_value="ctx + msg")),
        ):
            await service._run_impl("start", [])

        service.conversation_repo.update_external_session_id.assert_called_once_with(service.conversation, "brand_new")
        service.conversation_repo.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_host_stopped_after_run(self):
        """MCP host stop() is called after _run_impl completes."""
        service = _make_service(external_session_id="t1")

        mock_agent = MagicMock()
        mock_agent.thread_id = "t1"
        mock_agent.run = AsyncMock(
            return_value=TextMessage(
                role=MessageRole.AGENT,
                text_content="Done",
                timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )
        )

        mock_host = AsyncMock()
        mock_host.stop = AsyncMock()

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(mock_host, ()))),
        ):
            await service._run_impl("msg", [])

        mock_host.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_host_stopped_on_exception(self):
        """MCP host stop() is called even when agent.run raises."""
        service = _make_service(external_session_id="t1")

        mock_agent = MagicMock()
        mock_agent.thread_id = "t1"
        mock_agent.run = AsyncMock(side_effect=RuntimeError("run failed"))

        mock_host = AsyncMock()
        mock_host.stop = AsyncMock()

        with (
            patch.object(service, "_get_agent", return_value=mock_agent),
            patch.object(service, "_setup_mcp_host", new=AsyncMock(return_value=(mock_host, ()))),
        ):
            with pytest.raises(RuntimeError, match="run failed"):
                await service._run_impl("msg", [])

        mock_host.stop.assert_called_once()
