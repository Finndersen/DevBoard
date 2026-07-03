"""Codex agent implementation using the openai-codex SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator

import logfire
from openai_codex import ApprovalMode, AsyncCodex, AsyncThread, Sandbox
from openai_codex.client import CodexConfig
from pydantic_ai import Tool

from devboard.agents.base_agent import BaseAgent
from devboard.agents.engines.codex.event_converter import (
    convert_notification_to_events,
    convert_turn_result_to_text_message,
)
from devboard.agents.events import ContextUsage, ConversationEvent, TextMessage
from devboard.agents.language_models import LLMProvider
from devboard.agents.roles.base import AgentRole
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.models.language_model import LanguageModelDB


class CodexAgent(BaseAgent):
    """Agent backed by the openai-codex SDK.

    Each call to stream_events() or run() spawns a new Codex CLI process via AsyncCodex.
    Thread continuity is maintained via thread_id, which is updated after the first run
    and stored by the execution service as external_session_id.
    """

    def __init__(
        self,
        role: AgentRole,
        model: LanguageModelDB | None,
        thread_id: str | None = None,
        working_dir: str | None = None,
        additional_tools: list[Tool] | None = None,
        custom_instructions: str | None = None,
        config_overrides: tuple[str, ...] = (),
    ):
        if model is not None and model.provider != LLMProvider.OPENAI:
            raise ValueError(f"Unsupported model provider for Codex: {model.provider}")

        super().__init__(role, model, additional_tools, custom_instructions)

        self.thread_id = thread_id
        self.working_dir = working_dir
        self._config_overrides = config_overrides
        self._last_usage: ContextUsage | None = None

    def _build_codex_config(self) -> CodexConfig:
        return CodexConfig(config_overrides=self._config_overrides)

    async def _start_or_resume_thread(self, codex: AsyncCodex) -> AsyncThread:
        model_name = self.model.name if self.model else None
        system_prompt = self.get_full_system_prompt()

        if self.thread_id is None:
            logfire.info("Starting new Codex thread", working_dir=self.working_dir)
            thread = await codex.thread_start(
                cwd=self.working_dir,
                developer_instructions=system_prompt,
                model=model_name,
                sandbox=Sandbox.workspace_write,
                approval_mode=ApprovalMode.auto_review,
            )
            self.thread_id = thread.id
        else:
            logfire.info("Resuming Codex thread", thread_id=self.thread_id, working_dir=self.working_dir)
            thread = await codex.thread_resume(
                self.thread_id,
                cwd=self.working_dir,
                developer_instructions=system_prompt,
                model=model_name,
                sandbox=Sandbox.workspace_write,
            )
        return thread

    async def stream_events(self, prompt_or_approvals: str | ToolApprovals) -> AsyncIterator[ConversationEvent]:
        """Stream conversation events from Codex execution.

        Raises:
            ValueError: If ToolApprovals passed (Codex does not support approval workflow)
        """
        if isinstance(prompt_or_approvals, ToolApprovals):
            raise ValueError("Codex engine does not support tool approvals")

        prompt = prompt_or_approvals
        async with AsyncCodex(config=self._build_codex_config()) as codex:
            thread = await self._start_or_resume_thread(codex)
            turn_handle = await thread.turn(prompt)
            async for notification in turn_handle.stream():
                events, usage = convert_notification_to_events(notification)
                if usage is not None:
                    self._last_usage = usage
                for event in events:
                    yield event

    async def run(self, prompt: str) -> TextMessage:
        """Execute Codex non-interactively and return the final text response."""
        async with AsyncCodex(config=self._build_codex_config()) as codex:
            thread = await self._start_or_resume_thread(codex)
            result = await thread.run(prompt)

        if result.usage is not None:
            usage_breakdown = result.usage.last
            self._last_usage = ContextUsage(
                input_tokens=usage_breakdown.input_tokens,
                output_tokens=usage_breakdown.output_tokens,
                cache_read_tokens=usage_breakdown.cached_input_tokens,
                cache_write_tokens=0,
                cost_usd=None,
            )

        return convert_turn_result_to_text_message(result.final_response)

    def get_context_usage(self) -> ContextUsage | None:
        return self._last_usage
