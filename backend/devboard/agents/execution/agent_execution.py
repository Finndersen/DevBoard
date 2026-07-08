"""Abstract base interface for agent execution services."""

import asyncio
import datetime
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Literal

import logfire
from pydantic_ai import Tool
from sqlalchemy.orm import object_session

from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.events import (
    AgentRunCompletedEvent,
    AgentRunStartedEvent,
    ContextUsage,
    ConversationEvent,
    SystemEvent,
    SystemEventType,
    TextMessage,
)
from devboard.agents.exceptions import AgentInterruptedError
from devboard.agents.roles.base import AgentRole
from devboard.agents.system_message_tags import wrap_system_message
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.models import Conversation
from devboard.db.models.enums import EntityType
from devboard.db.repositories import ConversationRepository
from devboard.db.repositories.log_entry import LogEntryRepository
from devboard.mcp.mcp_tool_factory import MCPToolFactory
from devboard.services.oauth_service import OAuthService

if TYPE_CHECKING:
    from devboard.agents.agent_config_service import AgentConfigService


class AgentExecutionService(ABC):
    """Runs one agent turn within a known working directory.

    Manages MCP tool lifecycle, delegates to the engine via the template method
    pattern (`_stream_events_impl` / `_run_impl`), and emits `AgentRunStartedEvent`
    and `AgentRunCompletedEvent` as the first and last events of every stream,
    including on interrupt and failure paths.

    Instances are per-run: created by `create_agent_execution_service()` and
    discarded after the stream ends.
    """

    def __init__(
        self,
        conversation: Conversation,
        role: AgentRole,
        conversation_repository: ConversationRepository,
        history_service: ConversationHistoryService,
        agent_config_service: "AgentConfigService",
        working_dir: str,
        additional_tools: list[Tool] | None = None,
        oauth_service: OAuthService | None = None,
        interrupt_event: asyncio.Event | None = None,
        additional_write_dirs: list[str] | None = None,
        effort: Literal["low", "medium", "high"] | None = None,
        log_entry_repo: LogEntryRepository | None = None,
    ):
        self.conversation = conversation
        self.role = role
        self.conversation_repo = conversation_repository
        self._history_service = history_service
        self._agent_config_service = agent_config_service
        self.working_dir = working_dir
        self._additional_tools = additional_tools or []
        self._oauth_service = oauth_service
        self._interrupt_event = interrupt_event
        self.additional_write_dirs = additional_write_dirs
        self._effort = effort
        self._log_entry_repo = log_entry_repo

    async def _enrich_message(self, user_message: str, is_first_message: bool) -> str:
        """Enrich a user message with system context blocks.

        Prepends an initial_context block on the first message (enabling Claude API prompt
        caching by keeping the system prompt static), and an event_context block on every
        message when the role has configured event types to watch.

        Args:
            user_message: The raw user message string
            is_first_message: Whether this is the first message in the conversation

        Returns:
            The enriched message with any system context blocks prepended
        """
        parts: list[str] = []

        if is_first_message:
            context_content = await self.role.get_context_content()
            parts.append(wrap_system_message(context_content, "initial_context"))

            initial_instructions = self.role.get_initial_instructions()
            if initial_instructions:
                parts.append(wrap_system_message(initial_instructions, "initial_instructions"))

        if self.role.event_context_types and self._log_entry_repo is not None:
            event_context = self._build_event_context()
            if event_context:
                parts.append(wrap_system_message(event_context, "event_context"))

        parts.append(user_message)
        return "\n\n".join(parts)

    def _build_event_context(self) -> str | None:
        """Query relevant log entries and format them as an event context string.

        Returns None if there are no relevant events to inject.
        """
        from devboard.db.models.background_agent import BackgroundAgent
        from devboard.db.models.task import Task

        assert self._log_entry_repo is not None

        conversation = self.conversation
        entity_type = conversation.parent_entity_type

        if entity_type == EntityType.TASK:
            session = object_session(conversation)
            assert session is not None, "Conversation must be attached to a session"
            task = session.get(Task, conversation.parent_entity_id)
            if task is None:
                return None
            project_id = task.project_id
        elif entity_type == EntityType.PROJECT:
            project_id = conversation.parent_entity_id
        elif entity_type == EntityType.BACKGROUND_AGENT:
            session = object_session(conversation)
            assert session is not None, "Conversation must be attached to a session"
            agent = session.get(BackgroundAgent, conversation.parent_entity_id)
            if agent is None or agent.project_id is None:
                return None
            project_id = agent.project_id
        else:
            return None

        since = conversation.last_activity_at or conversation.created_at

        entries = self._log_entry_repo.query(
            project_id=project_id,
            types=self.role.event_context_types,
            since=since,
        )

        # Exclude events generated by this conversation itself
        entries = [
            e for e in entries if not (e.entry_metadata and e.entry_metadata.get("conversation_id") == conversation.id)
        ]

        if not entries:
            return None

        lines = ["The following system events occurred since your last interaction and may or may not be relevant"]
        for entry in reversed(entries):  # reverse to chronological order (repo returns desc)
            timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            line = f"- [{timestamp_str}] {entry.content}"
            if (
                entry.type == "task.merged"
                and entity_type == EntityType.TASK
                and entry.task_id != conversation.parent_entity_id
            ):
                line += (
                    "\n  Note: Another task's changes have been merged to the base branch. "
                    "Consider rebasing the current task branch to incorporate these changes if they may be relevant."
                )
            lines.append(line)

        return "\n".join(lines)

    def get_custom_instructions(self) -> str | None:
        """Get custom instructions for this agent role from config service."""
        config = self._agent_config_service.get_agent_configuration(self.conversation.agent_role)
        return config.custom_instructions

    def _enrich_context_usage(self, usage: ContextUsage) -> ContextUsage:
        """Populate context_window on ContextUsage from the conversation's model config."""
        if not self.conversation.model_id:
            return usage
        model = self._agent_config_service.get_model_by_id(self.conversation.model_id)
        if model and model.context_window:
            return usage.model_copy(update={"context_window": model.context_window})
        return usage

    async def send_message_or_approval(
        self,
        message: str,
    ) -> TextMessage:
        """Send a message through the agent and return the final text response.

        For non-interactive use only (sub-agents, background runs). Uses agent.run()
        to efficiently return only the final message without streaming.

        Args:
            message: The user message string to send to the agent

        Returns:
            The final TextMessage from the agent
        """
        with logfire.span(
            "agent_execution.send_message_or_approval",
            conversation_id=self.conversation.id,
        ):
            mcp_tool_configs = self._agent_config_service.get_enabled_mcp_tools(self.conversation.agent_role)
            async with MCPToolFactory(mcp_tool_configs, oauth_service=self._oauth_service) as mcp_factory:
                # MCP failures are logged (not returned) here because sub-agents have no UI
                # to surface SystemEvents; the streaming path yields them as SystemEvents instead.
                for failure in mcp_factory.setup_failures:
                    logfire.warning(
                        f"MCP server '{failure.server_name}' failed to connect: {failure.error}",
                        server_name=failure.server_name,
                        error=failure.error,
                    )
                extra_tools = self._additional_tools + mcp_factory.get_tools()
                return await self._run_impl(message, extra_tools)

    async def stream_events_for_message_or_approval(
        self,
        message_or_approvals: str | ToolApprovals,
    ) -> AsyncIterator[ConversationEvent]:
        """Stream conversation events from agent execution.

        Yields `AgentRunStartedEvent` as the first event, then all events from
        MCP setup and engine execution, and finally `AgentRunCompletedEvent` as
        the last event (even on interrupt or failure paths).

        `GeneratorExit` (consumer calling `.aclose()`) is caught to set a flag
        that suppresses the `yield` in the `finally` block — yielding in `finally`
        while `GeneratorExit` is active raises `RuntimeError`.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model

        Yields:
            ConversationEvent instances as they are generated during agent execution
        """
        is_approval = isinstance(message_or_approvals, ToolApprovals)
        status: Literal["completed", "interrupted", "failed"] = "completed"
        error: str | None = None
        cancelled = False
        last_usage: ContextUsage | None = None

        with logfire.span(
            "agent_execution.stream_events",
            conversation_id=self.conversation.id,
            engine=self.conversation.engine.value,
            is_approval=is_approval,
        ):
            yield AgentRunStartedEvent(
                conversation_id=self.conversation.id,
                timestamp=datetime.datetime.now(tz=datetime.UTC),
            )
            try:
                mcp_tool_configs = self._agent_config_service.get_enabled_mcp_tools(self.conversation.agent_role)
                async with MCPToolFactory(mcp_tool_configs, oauth_service=self._oauth_service) as mcp_factory:
                    for failure in mcp_factory.setup_failures:
                        yield SystemEvent(
                            sub_type=SystemEventType.STREAM_ERROR,
                            data={
                                "error_code": "MCP_SERVER_SETUP_FAILED",
                                "message": f"MCP server '{failure.server_name}' failed to connect: {failure.error}",
                            },
                            timestamp=datetime.datetime.now(tz=datetime.UTC),
                        )

                    # MCP server tools for the role plus any others added dynamically for the specific run
                    extra_tools = self._additional_tools + mcp_factory.get_tools()
                    async for event in self._stream_events_impl(message_or_approvals, extra_tools):
                        if isinstance(event, ContextUsage):
                            last_usage = self._enrich_context_usage(event)
                            continue  # out-of-band return value — not re-yielded
                        yield event
            except AgentInterruptedError:
                status = "interrupted"
                raise
            except GeneratorExit:
                cancelled = True
                raise
            except Exception as e:
                status = "failed"
                error = str(e)
                raise
            finally:
                if not cancelled:
                    yield AgentRunCompletedEvent(
                        status=status,
                        error=error,
                        usage=last_usage,
                        timestamp=datetime.datetime.now(tz=datetime.UTC),
                    )

    @abstractmethod
    async def _run_impl(
        self,
        message: str,
        extra_tools: list[Tool],
    ) -> TextMessage:
        """Engine-specific non-streaming execution.

        Subclasses implement this method to call agent.run() and return the final message.
        MCP tool lifecycle is managed by the parent `send_message_or_approval()`.

        Args:
            message: The user message string to send to the agent
            extra_tools: MCP server tools for the role plus any others added dynamically for the run

        Returns:
            The final TextMessage from the agent
        """

    @abstractmethod
    async def _stream_events_impl(
        self,
        message_or_approvals: str | ToolApprovals,
        extra_tools: list[Tool],
    ) -> AsyncIterator[ConversationEvent | ContextUsage]:
        """Engine-specific implementation of event streaming.

        Subclasses implement this method to handle the actual agent execution.
        MCP tool lifecycle is managed by the parent `stream_events_for_message_or_approval()`.

        Implementations should yield a `ContextUsage` as their final value to
        report the run's cumulative token usage. The base class intercepts it
        and attaches it to `AgentRunCompletedEvent`; it is never emitted to
        clients. This is the idiomatic way to "return" data from an async
        generator (PEP 525 disallows non-None return values).

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model
            extra_tools: MCP server tools for the role plus any others added dynamically for the run

        Yields:
            ConversationEvent instances as they are generated during agent execution,
            followed by a ContextUsage as the final out-of-band return value.
        """
        if False:
            yield  # type: ignore[unreachable]  # Required for async generator type inference
