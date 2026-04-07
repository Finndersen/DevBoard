"""PydanticAI conversation history service implementation."""

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelResponse, ToolCallPart, ToolReturnPart

from devboard.agents.conversation_history import ConversationHistory, ConversationHistoryService
from devboard.agents.engines.internal.utils import convert_tool_args
from devboard.agents.events import (
    ContextUsage,
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
    """

    async def get_conversation_history(self) -> ConversationHistory:
        db_messages = self.conversation_repo.get_messages(self.conversation.id)

        events: list[ConversationEvent] = []
        context_usage: ContextUsage | None = None

        for msg in db_messages:
            msg_events = self._db_message_to_events(msg)
            events.extend(msg_events)

            # Track usage from TEXT_RESPONSE messages (each overwrites the previous,
            # so we end up with usage from the last model response)
            if msg.message_type == MessageType.TEXT_RESPONSE:
                context_usage = self._extract_usage(msg)

        return ConversationHistory(messages=events, context_usage=context_usage)

    def _extract_usage(self, msg: DbConversationMessage) -> ContextUsage | None:
        """Extract context usage from a TEXT_RESPONSE database message."""
        pydantic_msgs = ModelMessagesTypeAdapter.validate_python([msg.pydantic_content])
        if not pydantic_msgs or not isinstance(pydantic_msgs[0], ModelResponse):
            return None
        usage = pydantic_msgs[0].usage
        if not (usage.input_tokens or usage.output_tokens or usage.cache_read_tokens or usage.cache_write_tokens):
            return None
        return ContextUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
        )

    def _db_message_to_events(self, msg: DbConversationMessage) -> list[ConversationEvent]:
        """Convert a database message to one or more ConversationEvent objects."""
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
            pydantic_msg = convert_messages_to_pydantic([msg])[0]
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
