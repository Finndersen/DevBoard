"""PydanticAI agent conversation service with deferred tools support."""

import logfire
from pydantic_ai.messages import ModelMessage, ToolCallPart, ToolReturnPart

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines.internal.agent import InternalAgent
from devboard.agents.events import ConversationEvent, ConversationMessage, MessageRole, ToolCall, ToolResult
from devboard.agents.language_models import llm_registry
from devboard.agents.roles.base import Role
from devboard.api.schemas.agent_conversation import (
    ToolApprovals,
)
from devboard.db.models import Conversation
from devboard.db.models.messages import ConversationMessage as DbConversationMessage
from devboard.db.models.messages import MessageType
from devboard.db.repositories.conversation import ConversationRepository


class PydanticAIConversationService(BaseAgentConversationService):
    """Service for handling internal PydanticAI agent conversations.

    This service manages conversations for PydanticAI-based agents, storing
    messages in the database and handling tool approval workflows.

    Attributes:
        conversation: The conversation instance (from base class)
        role: The Role defining agent behavior
        conversation_repo: Repository for database operations
    """

    def __init__(
        self,
        conversation: Conversation,
        role: Role,
        conversation_repository: ConversationRepository,
    ):
        """Initialize PydanticAI conversation service.

        Args:
            conversation: The conversation instance to manage
            role: The Role defining agent behavior
            conversation_repository: Repository for conversation database operations
        """
        super().__init__(conversation, role, conversation_repository)

    @property
    def conversation_id(self) -> int:
        """Get the conversation ID from the conversation instance."""
        return self.conversation.id

    async def send_message_or_approval(
        self,
        message_or_approvals: str | ToolApprovals,
    ) -> list[ConversationEvent]:
        """Send a message or process tool approvals through the agent.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model

        Returns:
            List of conversation events generated during agent execution
        """
        is_approval = isinstance(message_or_approvals, ToolApprovals)

        with logfire.span(
            "agent_conversation.send_message_or_approval",
            conversation_id=self.conversation.id,
            is_approval=is_approval,
        ):
            return await self._handle_message_or_approval(message_or_approvals=message_or_approvals)

    def _get_agent(self, conversation_history: list[ModelMessage]) -> InternalAgent:
        """Create and return an agent instance.

        This method can be patched in tests to return a mock agent.

        Args:
            conversation_history: Previous conversation messages

        Returns:
            InternalAgent instance configured with role, model, and history
        """
        model = llm_registry.get(self.conversation.model_id)
        return InternalAgent(
            role=self.role,
            model=model,
            conversation_history=conversation_history,
        )

    async def _handle_message_or_approval(self, message_or_approvals: str | ToolApprovals) -> list[ConversationEvent]:
        """
        Handle either a new user message or tool approval result.
        :param message_or_approvals: User message/prompt or tool approval model
        :return: List of conversation events
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

        message_history = self.conversation_repo.convert_messages_to_pydantic(existing_messages)

        # Create agent with history and deps
        agent = self._get_agent(conversation_history=message_history)

        # Execute agent
        events = await agent.run(message_or_approvals)

        # Persist new messages
        new_messages = agent.get_new_messages()
        self._store_new_messages(new_messages=new_messages)

        return events

    def _get_message_history(self) -> list[DbConversationMessage]:
        return self.conversation_repo.get_messages(self.conversation.id)

    def _store_new_messages(self, new_messages: list[ModelMessage]) -> list[DbConversationMessage]:
        """Store new messages from agent result in DB."""
        # Extract all messages from the agent result
        saved_messages = []
        for message in new_messages:
            saved_messages.append(self.conversation_repo.create_message(self.conversation.id, message))
        return saved_messages

    async def get_conversation_messages(self) -> list[ConversationEvent]:
        """Retrieve all messages for the PydanticAI conversation.

        Messages are queried from the database and converted to ConversationEvent objects
        that include text messages, tool calls, and tool results.

        Returns:
            List of ConversationEvent instances in chronological order
        """
        db_messages = self.conversation_repo.get_messages(self.conversation.id)

        events: list[ConversationEvent] = []

        for msg in db_messages:
            # Convert each database message to appropriate ConversationEvent type(s)
            msg_events = self._db_message_to_events(msg)
            events.extend(msg_events)

        return events

    def _db_message_to_events(self, msg: DbConversationMessage) -> list[ConversationEvent]:
        """Convert a database message to one or more ConversationEvent objects.

        Args:
            msg: Database conversation message

        Returns:
            List of ConversationEvent objects representing the message content
        """
        events: list[ConversationEvent] = []

        if msg.message_type == MessageType.USER_PROMPT:
            # User prompt - single text message
            events.append(
                ConversationMessage(
                    role=MessageRole.USER,
                    text_content=msg.text_content,
                    timestamp=msg.timestamp,
                )
            )
        elif msg.message_type == MessageType.TEXT_RESPONSE:
            # Agent text response - single text message
            events.append(
                ConversationMessage(
                    role=MessageRole.AGENT,
                    text_content=msg.text_content,
                    timestamp=msg.timestamp,
                )
            )
        elif msg.message_type in (MessageType.TOOL_CALL, MessageType.TOOL_RESULT, MessageType.STRUCTURED_RESPONSE):
            # For messages containing tool calls/results, we need to parse the PydanticAI message
            pydantic_msg = self.conversation_repo.convert_messages_to_pydantic([msg])[0]
            # Extract parts from the message
            for part in pydantic_msg.parts:
                if isinstance(part, ToolCallPart):
                    events.append(
                        ToolCall(
                            tool_call_id=part.tool_call_id,
                            tool_name=part.tool_name,
                            tool_args=part.args,
                            timestamp=msg.timestamp,
                        )
                    )
                elif isinstance(part, ToolReturnPart):
                    events.append(
                        ToolResult(
                            tool_call_id=part.tool_call_id,
                            result_content=str(part.content),
                            is_error=False,
                            timestamp=msg.timestamp,
                        )
                    )

        return events
