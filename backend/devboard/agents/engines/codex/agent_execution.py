"""Codex agent execution service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import logfire
from pydantic_ai import Tool

from devboard.agents.engines.codex.agent import CodexAgent
from devboard.agents.engines.codex.mcp_host import HarnessMCPHost, create_mcp_server_from_tools
from devboard.agents.events import ContextUsage, ConversationEvent, SystemEvent, SystemEventType, TextMessage
from devboard.agents.exceptions import AgentInterruptedError
from devboard.agents.execution.agent_execution import AgentExecutionService
from devboard.api.schemas.agent_conversation import ToolApprovals


class CodexAgentExecutionService(AgentExecutionService):
    """Execution service for Codex-backed agents.

    Manages MCP host lifecycle (one per run) and Codex thread ID persistence.
    Codex does not support virtual tools or ToolApprovals; all tools are served
    via the MCP HTTP host registered in the Codex CLI config.
    """

    @property
    def thread_id(self) -> str | None:
        return self.conversation.external_session_id

    async def _setup_mcp_host(self, extra_tools: list[Tool]) -> tuple[HarnessMCPHost | None, tuple[str, ...]]:
        """Start an MCP host serving extra_tools and return (host, config_overrides).

        Returns (None, ()) when no tools are provided.
        """
        if not extra_tools:
            return None, ()
        mcp_host = HarnessMCPHost()
        server = create_mcp_server_from_tools("devboard_tools", extra_tools)
        mcp_host.add_server("devboard_tools", server)
        await mcp_host.start()
        overrides: list[str] = []
        for name, config in mcp_host.mcp_config_entries().items():
            for key, value in config.items():
                if isinstance(value, bool):
                    overrides.append(f"mcp_servers.{name}.{key}={str(value).lower()}")
                elif isinstance(value, str):
                    overrides.append(f'mcp_servers.{name}.{key}="{value}"')
                else:
                    overrides.append(f"mcp_servers.{name}.{key}={value}")
        return mcp_host, tuple(overrides)

    async def _stream_events_impl(
        self,
        message_or_approvals: str | ToolApprovals,
        extra_tools: list[Tool],
    ) -> AsyncIterator[ConversationEvent | ContextUsage]:
        if isinstance(message_or_approvals, str) and self.thread_id is None:
            message_or_approvals = await self._build_context_message(message_or_approvals)

        mcp_host, config_overrides = await self._setup_mcp_host(extra_tools)

        try:
            agent = self._get_agent(extra_tools=extra_tools, config_overrides=config_overrides)

            async for event in agent.stream_events(message_or_approvals):
                if agent.thread_id != self.conversation.external_session_id:
                    logfire.info(
                        f"Updating Codex conversation {self.conversation.id} thread ID from "
                        f"{self.conversation.external_session_id} to {agent.thread_id}"
                    )
                    self.conversation_repo.update_external_session_id(self.conversation, agent.thread_id)
                    self.conversation_repo.commit()
                    yield SystemEvent(
                        sub_type=SystemEventType.CONVERSATION_UPDATED,
                        data={
                            "conversation_id": self.conversation.id,
                            "updated_fields": {"external_session_id": agent.thread_id},
                        },
                        timestamp=datetime.now(UTC),
                    )

                yield event

            usage = agent.get_context_usage()
            if usage is not None:
                yield usage

            if self._interrupt_event and self._interrupt_event.is_set():
                logfire.info(f"Codex agent execution interrupted for conversation {self.conversation.id}")
                raise AgentInterruptedError("Agent execution interrupted")

        finally:
            if mcp_host is not None:
                await mcp_host.stop()

    async def _run_impl(
        self,
        message: str,
        extra_tools: list[Tool],
    ) -> TextMessage:
        if self.thread_id is None:
            message = await self._build_context_message(message)

        mcp_host, config_overrides = await self._setup_mcp_host(extra_tools)

        try:
            agent = self._get_agent(extra_tools=extra_tools, config_overrides=config_overrides)
            result = await agent.run(message)

            if agent.thread_id != self.conversation.external_session_id:
                logfire.info(
                    f"Updating Codex conversation {self.conversation.id} thread ID from "
                    f"{self.conversation.external_session_id} to {agent.thread_id}"
                )
                self.conversation_repo.update_external_session_id(self.conversation, agent.thread_id)
                self.conversation_repo.commit()

            return result
        finally:
            if mcp_host is not None:
                await mcp_host.stop()

    def _get_agent(self, extra_tools: list[Tool] | None = None, config_overrides: tuple[str, ...] = ()) -> CodexAgent:
        db_model = (
            self._agent_config_service.get_model_by_id(self.conversation.model_id)
            if self.conversation.model_id
            else None
        )
        return CodexAgent(
            role=self.role,
            model=db_model,
            thread_id=self.conversation.external_session_id,
            working_dir=self.working_dir,
            additional_tools=extra_tools or [],
            custom_instructions=self.get_custom_instructions(),
            config_overrides=config_overrides,
        )
