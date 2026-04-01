"""PydanticAI conversation history service implementation."""

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelResponse, ToolCallPart, ToolReturnPart

from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.engines.internal.utils import convert_tool_args
from devboard.agents.events import (
    ConversationEvent,
    MessageRole,
    MetaMessage,
    MetaMessageType,
    TextMessage,
    ToolCall,
    ToolResult,
)
from devboard.agents.system_message_tags import extract_system_messages
from devboard.db.models.messages import ConversationMessage as DbConversationMessage
from devboard.db.models.messages import MessageType


class PydanticAIConversationHistoryService(ConversationHistoryService):
    """Service for retrieving conversation history from PydanticAI conversations.

    This service retrieves messages stored in the database and converts them
    to ConversationEvent format for display.

    Attributes:
        conversation: The conversation instance (from base class)
        conversation_repo: Repository for database operations
    """

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
            sys_blocks, remaining = extract_system_messages(msg.text_content)
            for block in sys_blocks:
                events.append(
                    MetaMessage(
                        meta_type=MetaMessageType(block.message_type),
                        text_content=block.content,
                        timestamp=msg.timestamp,
                    )
                )
            if remaining:
                events.append(
                    TextMessage(
                        role=MessageRole.USER,
                        text_content=remaining,
                        timestamp=msg.timestamp,
                    )
                )
        elif msg.message_type == MessageType.TEXT_RESPONSE:
            # Agent text response - single text message
            # Extract model_name from serialized pydantic_content if available
            model_name: str | None = None
            pydantic_msgs = ModelMessagesTypeAdapter.validate_python([msg.pydantic_content])
            if pydantic_msgs and isinstance(pydantic_msgs[0], ModelResponse):
                model_name = pydantic_msgs[0].model_name
            events.append(
                TextMessage(
                    role=MessageRole.AGENT,
                    text_content=msg.text_content,
                    timestamp=msg.timestamp,
                    model=model_name,
                )
            )
        elif msg.message_type in (MessageType.TOOL_CALL, MessageType.TOOL_RESULT, MessageType.STRUCTURED_RESPONSE):
            # For messages containing tool calls/results, we need to parse the PydanticAI message
            pydantic_msg = convert_messages_to_pydantic([msg])[0]
            # Extract parts from the message
            for part in pydantic_msg.parts:
                if isinstance(part, ToolCallPart):
                    events.append(
                        ToolCall(
                            tool_call_id=part.tool_call_id,
                            tool_name=part.tool_name,
                            tool_args=convert_tool_args(part.args),
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


def convert_messages_to_pydantic(message_records: list[DbConversationMessage]) -> list[ModelMessage]:
    """Extract PydanticAI message history from database records.

    This is a module-level function that can be used by both the history service
    and the execution service.

    Args:
        message_records: List of database conversation message records

    Returns:
        List of PydanticAI ModelMessage objects
    """
    # Extract pydantic_content from each record
    serialized_messages = [record.pydantic_content for record in message_records]

    if not serialized_messages:
        return []

    # Deserialize the messages
    messages = ModelMessagesTypeAdapter.validate_python(serialized_messages)
    return messages
