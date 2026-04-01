"""PydanticAI agent execution service implementation."""

from collections.abc import AsyncIterator

import logfire
from pydantic_ai import Tool
from pydantic_ai.messages import ModelMessage

from devboard.agents.engines.internal.agent import InternalAgent
from devboard.agents.engines.internal.conversation_history import convert_messages_to_pydantic
from devboard.agents.events import ConversationEvent, TextMessage
from devboard.agents.exceptions import AgentInterruptedError
from devboard.agents.execution.agent_execution import AgentExecutionService
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

    async def _run_impl(
        self,
        message: str,
        extra_tools: list[Tool],
    ) -> TextMessage:
        """Non-streaming execution via InternalAgent.run().

        Loads history, validates integrity, runs to completion, stores new messages.
        """
        existing_messages = self._get_message_history()
        if existing_messages and existing_messages[-1].message_type == MessageType.TOOL_CALL:
            delete_count = self.conversation_repo.delete_tool_approval_messages(self.conversation.id)
            existing_messages = existing_messages[:-delete_count]
            logfire.warning(f"Deleted {delete_count} messages due to missing tool approvals")

        message_history = convert_messages_to_pydantic(existing_messages)
        agent = self._get_agent(conversation_history=message_history, extra_tools=extra_tools)
        result = await agent.run(message)
        self._store_new_messages(agent.get_new_messages())
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

        agent = self._get_agent(conversation_history=message_history, extra_tools=extra_tools)

        async for event in agent.stream_events(message_or_approvals):
            if self._interrupt_event and self._interrupt_event.is_set():
                logfire.info(f"PydanticAI agent execution interrupted for conversation {self.conversation.id}")
                raise AgentInterruptedError("Agent execution interrupted")

            yield event

        # Check interrupt flag after the loop in case it was set just as the final event arrived.
        if self._interrupt_event and self._interrupt_event.is_set():
            logfire.info(f"PydanticAI agent execution interrupted (post-loop) for conversation {self.conversation.id}")
            raise AgentInterruptedError("Agent execution interrupted")

        self._store_new_messages(agent.get_new_messages())

    def _get_agent(
        self, conversation_history: list[ModelMessage], extra_tools: list[Tool] | None = None
    ) -> InternalAgent:
        """Create and return an agent instance.

        This method can be patched in tests to return a mock agent.

        Args:
            conversation_history: Previous conversation messages
            extra_tools: Combined MCP and dynamically-added tools

        Returns:
            InternalAgent instance configured with role, model, and history
        """
        db_model = (
            self._agent_config_service.get_model_by_id(self.conversation.model_id)
            if self.conversation.model_id
            else None
        )
        if not db_model:
            raise ValueError(f"Model '{self.conversation.model_id}' not found in registry")

        return InternalAgent(
            role=self.role,
            model=db_model,
            conversation_history=conversation_history,
            additional_tools=extra_tools or [],
            custom_instructions=self.get_custom_instructions(),
        )

    def _get_message_history(self) -> list[DbConversationMessage]:
        return self.conversation_repo.get_messages(self.conversation.id)

    def _store_new_messages(self, new_messages: list[ModelMessage]) -> list[DbConversationMessage]:
        """Store new messages from agent result in DB."""
        # Extract all messages from the agent result
        saved_messages: list[DbConversationMessage] = []
        for message in new_messages:
            saved_messages.append(self.conversation_repo.create_message(self.conversation.id, message))
        return saved_messages
