"""PydanticAI agent execution service implementation."""

import asyncio
from collections.abc import AsyncIterator

import logfire
from pydantic_ai import Tool
from pydantic_ai.messages import ModelMessage

from devboard.agents.agent_execution import AgentExecutionService
from devboard.agents.engines.internal.agent import InternalAgent
from devboard.agents.engines.internal.conversation_history import convert_messages_to_pydantic
from devboard.agents.events import ConversationEvent
from devboard.agents.language_models import llm_registry
from devboard.api.schemas.agent_conversation import ToolApprovals
from devboard.db.models.messages import ConversationMessage as DbConversationMessage
from devboard.db.models.messages import MessageType


class PydanticAIAgentExecutionService(AgentExecutionService):
    """Service for executing PydanticAI agent conversations.

    This service manages execution for PydanticAI-based agents, storing
    messages in the database and handling tool approval workflows.

    Attributes:
        conversation: The conversation instance (from base class)
        role: The Role defining agent behavior
        conversation_repo: Repository for database operations
    """

    @property
    def conversation_id(self) -> int:
        """Get the conversation ID from the conversation instance."""
        return self.conversation.id

    async def _stream_events_impl(
        self,
        message_or_approvals: str | ToolApprovals,
        mcp_tools: list[Tool],
    ) -> AsyncIterator[ConversationEvent]:
        """Engine-specific implementation of event streaming.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model
            mcp_tools: PydanticAI Tool instances from enabled MCP servers

        Yields:
            ConversationEvent instances as they are generated during agent execution
        """
        # Load conversation history
        existing_messages = self._get_message_history()
        # Verify integrity of message history
        if isinstance(message_or_approvals, ToolApprovals):
            if not existing_messages:
                raise ValueError("No existing messages found for processing tool approvals.")
            if existing_messages[-1].message_type != MessageType.TOOL_CALL:
                raise ValueError("Last message is not a tool call; cannot process approvals.")
        else:
            if existing_messages and existing_messages[-1].message_type == MessageType.TOOL_CALL:
                # If there was an issue processing tool approvals or they were never provided,
                # need to clear the message history until previous message
                delete_count = self.conversation_repo.delete_tool_approval_messages(self.conversation.id)
                existing_messages = existing_messages[:-delete_count]
                logfire.warning(f"Deleted {delete_count} messages due to missing tool approvals")

        message_history = convert_messages_to_pydantic(existing_messages)

        # Create agent with history, deps, and MCP tools
        agent = self._get_agent(conversation_history=message_history, mcp_tools=mcp_tools)

        # Stream events from agent execution
        try:
            async for event in agent.stream_events(message_or_approvals):
                yield event

            # Persist new messages after streaming completes
            new_messages = agent.get_new_messages()
            self._store_new_messages(new_messages=new_messages)
        except asyncio.CancelledError:
            logfire.info(f"PydanticAI agent execution cancelled for conversation {self.conversation.id}")
            raise

    def _get_agent(
        self, conversation_history: list[ModelMessage], mcp_tools: list[Tool] | None = None
    ) -> InternalAgent:
        """Create and return an agent instance.

        This method can be patched in tests to return a mock agent.

        Args:
            conversation_history: Previous conversation messages
            mcp_tools: Optional MCP tools to include as additional tools

        Returns:
            InternalAgent instance configured with role, model, and history
        """
        model = llm_registry.get(self.conversation.model_id) if self.conversation.model_id else None
        if not model:
            raise ValueError(f"Model '{self.conversation.model_id}' not found in registry")

        # Combine additional_tools with MCP tools
        all_additional_tools = self.additional_tools + (mcp_tools or [])

        return InternalAgent(
            role=self.role,
            model=model,
            conversation_history=conversation_history,
            additional_tools=all_additional_tools,
            custom_instructions=self.get_custom_instructions(),
        )

    def _get_message_history(self) -> list[DbConversationMessage]:
        return self.conversation_repo.get_messages(self.conversation.id)

    def _store_new_messages(self, new_messages: list[ModelMessage]) -> list[DbConversationMessage]:
        """Store new messages from agent result in DB."""
        # Extract all messages from the agent result
        saved_messages = []
        for message in new_messages:
            saved_messages.append(self.conversation_repo.create_message(self.conversation.id, message))
        return saved_messages
