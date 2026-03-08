"""Abstract base interface for agent execution services."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import logfire
from pydantic_ai import Tool

from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.events import ConversationEvent
from devboard.agents.roles.base import AgentRole
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.models import Conversation
from devboard.db.repositories import ConversationRepository
from devboard.mcp.mcp_tool_factory import MCPToolFactory
from devboard.services.oauth_service import OAuthService

if TYPE_CHECKING:
    from devboard.agents.agent_config_service import AgentConfigService


class AgentExecutionService(ABC):
    """Abstract base class for agent execution services.

    This class uses the template method pattern for agent execution:
    - `stream_events_for_message_or_approval()` handles MCP tool lifecycle
    - `_stream_events_impl()` is implemented by subclasses for engine-specific execution

    Implementations should handle:
    - Agent initialization and configuration
    - Message/approval processing
    - Tool approval workflows
    - Response formatting and event streaming

    Attributes:
        conversation: The conversation instance this service manages
        role: The Role defining agent behavior
        conversation_repo: Repository for conversation operations
        agent_config_service: Service for loading agent configuration (custom instructions, MCP tools)
    """

    def __init__(
        self,
        conversation: Conversation,
        role: AgentRole,
        conversation_repository: ConversationRepository,
        history_service: ConversationHistoryService,
        agent_config_service: "AgentConfigService",
        additional_tools: list[Tool] | None = None,
        oauth_service: OAuthService | None = None,
    ):
        """Initialize the agent execution service.

        Args:
            conversation: The conversation instance to manage
            role: The Role defining agent behavior
            conversation_repository: Repository for conversation operations
            history_service: Service for retrieving conversation history
            agent_config_service: Service for loading agent configuration
            additional_tools: Optional list of additional tools to provide to the agent,
                beyond those defined by the role. Used for workflow-action-specific tools.
            oauth_service: Optional OAuthService for OAuth-authenticated MCP servers.
        """
        self.conversation = conversation
        self.role = role
        self.conversation_repo = conversation_repository
        self._history_service = history_service
        self._agent_config_service = agent_config_service
        self._additional_tools = additional_tools or []
        self._oauth_service = oauth_service

    def get_custom_instructions(self) -> str | None:
        """Get custom instructions for this agent role from config service."""
        config = self._agent_config_service.get_agent_configuration(self.conversation.agent_role)
        return config.custom_instructions

    async def send_message_or_approval(
        self,
        message_or_approvals: str | ToolApprovals,
    ) -> list[ConversationEvent]:
        """Send a message or process tool approvals through the agent.

        Wraps the streaming method to collect all events into a list.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model

        Returns:
            List of conversation events generated during agent execution
        """
        is_approval = isinstance(message_or_approvals, ToolApprovals)

        with logfire.span(
            "agent_execution.send_message_or_approval",
            conversation_id=self.conversation.id,
            is_approval=is_approval,
        ):
            # Collect all events from the stream
            events: list[ConversationEvent] = []
            async for event in self.stream_events_for_message_or_approval(message_or_approvals):
                events.append(event)
            return events

    async def stream_events_for_message_or_approval(
        self,
        message_or_approvals: str | ToolApprovals,
    ) -> AsyncIterator[ConversationEvent]:
        """Stream conversation events from agent execution.

        This method handles MCP tool lifecycle (connecting/disconnecting to MCP servers)
        and delegates to `_stream_events_impl()` for engine-specific execution.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model

        Yields:
            ConversationEvent instances as they are generated during agent execution
        """
        is_approval = isinstance(message_or_approvals, ToolApprovals)

        with logfire.span(
            "agent_execution.stream_events",
            conversation_id=self.conversation.id,
            engine=self.conversation.engine.value,
            is_approval=is_approval,
        ):
            mcp_tool_configs = self._agent_config_service.get_enabled_mcp_tools(self.conversation.agent_role)
            async with MCPToolFactory(mcp_tool_configs, oauth_service=self._oauth_service) as mcp_factory:
                # MCP server tools for the role plus any others added dynamically for the specific run
                extra_tools = self._additional_tools + mcp_factory.get_tools()
                async for event in self._stream_events_impl(message_or_approvals, extra_tools):
                    yield event

    @abstractmethod
    async def _stream_events_impl(
        self,
        message_or_approvals: str | ToolApprovals,
        extra_tools: list[Tool],
    ) -> AsyncIterator[ConversationEvent]:
        """Engine-specific implementation of event streaming.

        Subclasses implement this method to handle the actual agent execution.
        MCP tool lifecycle is managed by the parent `stream_events_for_message_or_approval()`.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model
            extra_tools: MCP server tools for the role plus any others added dynamically for the run

        Yields:
            ConversationEvent instances as they are generated during agent execution
        """
        if False:
            yield  # type: ignore[unreachable]  # Required for async generator type inference
