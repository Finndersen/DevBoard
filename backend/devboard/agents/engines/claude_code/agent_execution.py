"""Claude Code agent execution service implementation."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import logfire
from pydantic_ai import Tool

from devboard.agents.engines.claude_code.agent import ClaudeCodeAgent
from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType, TextMessage
from devboard.agents.exceptions import AgentInterruptedError
from devboard.agents.execution.agent_execution import AgentExecutionService
from devboard.api.schemas.agent_conversation import ToolApprovals


class ClaudeCodeAgentExecutionService(AgentExecutionService):
    """Service for executing Claude Code agent conversations.

    This service manages execution for Claude Code agents, handling session
    continuity and virtual tool approval workflows.

    Note: Claude Code manages its own session files. This service does NOT
    store messages in the database - it reads from session files as needed.

    MCP tools are supported and passed to ClaudeCodeAgent as additional_tools.
    These are converted to function tools that Claude Code can invoke.

    Attributes:
        conversation: The conversation instance (from base class)
        role: The Role defining agent behavior
        conversation_repo: Repository for conversation operations
    """

    @property
    def session_id(self) -> str | None:
        """Get the current Claude session ID from the conversation."""
        return self.conversation.external_session_id

    async def _run_impl(
        self,
        message: str,
        extra_tools: list[Tool],
    ) -> TextMessage:
        """Non-streaming execution via ClaudeCodeAgent.run().

        Updates session_id in the database after the run completes.
        """
        agent = self._get_agent(extra_tools=extra_tools)

        try:
            result = await agent.run(message)
        except FileNotFoundError:
            logfire.warn(f"Session file not found during run for conversation {self.conversation.id}")
            raise

        if agent.session_id != self.conversation.external_session_id:
            logfire.info(
                f"Updating conversation {self.conversation.id} Session ID from "
                f"{self.conversation.external_session_id} to {agent.session_id}"
            )
            self.conversation_repo.update_external_session_id(self.conversation, agent.session_id)
            self.conversation_repo.commit()

        return result

    async def _stream_events_impl(
        self,
        message_or_approvals: str | ToolApprovals,
        extra_tools: list[Tool],
    ) -> AsyncIterator[ConversationEvent]:
        """Engine-specific implementation of event streaming.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model
            extra_tools: MCP server tools for the role plus any others added dynamically for the run

        Yields:
            ConversationEvent instances as they are generated during agent execution
        """
        # Check session ID for approvals
        if isinstance(message_or_approvals, ToolApprovals) and not self.session_id:
            raise ValueError("No session ID available - cannot process tool approvals")

        agent = self._get_agent(extra_tools=extra_tools)

        # Stream events from agent execution
        try:
            async for event in agent.stream_events(message_or_approvals, interrupt_event=self._interrupt_event):
                # Update session_id if changed
                if agent.session_id != self.conversation.external_session_id:
                    logfire.info(
                        f"Updating conversation {self.conversation.id} Session ID from {self.conversation.external_session_id} to {agent.session_id}"
                    )
                    self.conversation_repo.update_external_session_id(self.conversation, agent.session_id)
                    self.conversation_repo.commit()
                    yield SystemEvent(
                        type=SystemEventType.CONVERSATION_UPDATED,
                        data={
                            "conversation_id": self.conversation.id,
                            "updated_fields": {"external_session_id": agent.session_id},
                        },
                        timestamp=datetime.now(UTC),
                    )

                yield event

            if self._interrupt_event and self._interrupt_event.is_set():
                logfire.info(f"Claude Code agent execution interrupted for conversation {self.conversation.id}")
                raise AgentInterruptedError("Agent execution interrupted")
        except FileNotFoundError:
            logfire.warn(
                f"Session file not found during streaming for conversation {self.conversation.id}, session ID preserved"
            )
            yield SystemEvent(
                type=SystemEventType.SESSION_EXPIRED,
                data={"message": "Claude Code session file not found. Clear this conversation to start a new one."},
                timestamp=datetime.now(UTC),
            )

    def _get_agent(self, extra_tools: list[Tool] | None = None) -> ClaudeCodeAgent:
        """Create agent with session_id and optional extra tools."""
        db_model = (
            self._agent_config_service.get_model_by_id(self.conversation.model_id)
            if self.conversation.model_id
            else None
        )

        return ClaudeCodeAgent(
            role=self.role,
            model=db_model,
            session_id=self.conversation.external_session_id,
            working_dir=self.working_dir,
            additional_tools=extra_tools or [],
            custom_instructions=self.get_custom_instructions(),
        )
