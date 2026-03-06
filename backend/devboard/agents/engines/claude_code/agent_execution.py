"""Claude Code agent execution service implementation."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import logfire
from pydantic_ai import Tool

from devboard.agents.agent_execution import AgentExecutionService
from devboard.agents.engines.claude_code.agent import ClaudeCodeAgent
from devboard.agents.events import ConversationEvent, SystemEvent, SystemEventType
from devboard.agents.language_models import llm_registry
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.models import Codebase, Task


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
            async for event in agent.stream_events(message_or_approvals):
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
        except asyncio.CancelledError:
            logfire.info(f"Claude Code agent execution cancelled for conversation {self.conversation.id}")
            raise
        except FileNotFoundError:
            # Session file was cleaned up - reset session ID and notify user
            logfire.info(
                f"Session file not found during streaming for conversation {self.conversation.id}, resetting session ID"
            )
            self.conversation_repo.update_external_session_id(self.conversation, None)
            self.conversation_repo.commit()
            yield SystemEvent(
                type=SystemEventType.SESSION_EXPIRED,
                data={"message": "Claude session was cleaned up, starting new conversation"},
                timestamp=datetime.now(UTC),
            )

    def _get_agent(self, extra_tools: list[Tool] | None = None) -> ClaudeCodeAgent:
        """Create agent with session_id and optional extra tools.

        Args:
            extra_tools: Combined MCP and dynamically-added tools

        Returns:
            ClaudeCodeAgent instance configured with role, model, and tools
        """
        model = llm_registry.get(self.conversation.model_id) if self.conversation.model_id else None
        conversation_parent = self.conversation.get_parent_entity()
        if isinstance(conversation_parent, Task):
            codebase_path = conversation_parent.get_current_workspace_dir()
        elif isinstance(conversation_parent, Codebase):
            codebase_path = conversation_parent.local_path
        else:
            codebase_path = None

        return ClaudeCodeAgent(
            role=self.role,
            model=model,
            session_id=self.conversation.external_session_id,
            working_dir=codebase_path,
            additional_tools=extra_tools or [],
            custom_instructions=self.get_custom_instructions(),
        )
