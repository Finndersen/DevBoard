"""Convert stored SessionMessage objects to ConversationEvents.

Pure function that transforms JSONL-parsed SessionMessage objects into the
application's ConversationEvent types for history replay. This is the stored-session
counterpart to message_converter.py which handles live SDK Message objects.
"""

from devboard.agents.engines.claude_code.message_parser import (
    ClaudeResponseParser,
    TextResponse,
    VirtualToolCall,
    convert_virtual_tool_call_to_events,
)
from devboard.agents.engines.claude_code.session.models import (
    AssistantSessionMessage,
    LocalCommandSessionMessage,
    MetaSessionMessage,
    SessionMessage,
    UserSessionMessage,
)
from devboard.agents.engines.claude_code.utils import normalize_tool_name
from devboard.agents.events import (
    ConversationEvent,
    LocalCommand,
    MessageRole,
    MetaMessage,
    TextMessage,
    ThinkingEvent,
    ToolCall,
    ToolResult,
)


def session_messages_to_events(
    session_messages: list[SessionMessage], *, include_sidechain: bool = False
) -> list[ConversationEvent]:
    """Convert session messages to conversation events.

    Expands each SessionMessage.content list into separate events, providing a complete
    timeline of the conversation including tool calls and results.

    Filters out sidechain messages and invalid tool calls.
    """
    events: list[ConversationEvent] = []
    message_count = len(session_messages)
    for session_idx, session_msg in enumerate(session_messages):
        if session_msg.is_sidechain and not include_sidechain:
            continue

        if isinstance(session_msg, MetaSessionMessage):
            events.append(
                MetaMessage(
                    meta_type=session_msg.meta_type,
                    text_content=session_msg.text_content,
                    timestamp=session_msg.timestamp,
                    uuid=session_msg.uuid,
                )
            )
            continue

        if isinstance(session_msg, LocalCommandSessionMessage):
            events.append(
                LocalCommand(
                    command_type=session_msg.command_type,
                    command=session_msg.command,
                    output=session_msg.output,
                    is_error=session_msg.is_error,
                    timestamp=session_msg.timestamp,
                    uuid=session_msg.uuid,
                )
            )
            continue

        session_model = session_msg.model if isinstance(session_msg, AssistantSessionMessage) else None
        for content_block in session_msg.content:
            if content_block["type"] == "thinking":
                events.append(
                    ThinkingEvent(
                        thinking_text=content_block.get("thinking"),
                        timestamp=session_msg.timestamp,
                        uuid=session_msg.uuid,
                    )
                )

            elif content_block["type"] == "text":
                parsed = ClaudeResponseParser.parse_message_content(content_block["text"])

                if isinstance(parsed, TextResponse):
                    conv_role = MessageRole.USER if isinstance(session_msg, UserSessionMessage) else MessageRole.AGENT
                    events.append(
                        TextMessage(
                            role=conv_role,
                            text_content=parsed.content,
                            timestamp=session_msg.timestamp,
                            uuid=session_msg.uuid,
                            model=session_model,
                        )
                    )

                elif isinstance(parsed, VirtualToolCall):
                    tool_call_events = convert_virtual_tool_call_to_events(
                        tool_call=parsed,
                        timestamp=session_msg.timestamp,
                        use_tool_call_request=session_idx == message_count - 1,
                        model=session_model,
                    )
                    for event in tool_call_events:
                        event.uuid = session_msg.uuid
                    events.extend(tool_call_events)

                else:
                    # VirtualToolResult
                    events.append(
                        ToolResult(
                            tool_call_id=parsed.tool_name,
                            result_content=parsed.content,
                            is_error=not parsed.successful,
                            timestamp=session_msg.timestamp,
                            uuid=session_msg.uuid,
                        )
                    )

            elif content_block["type"] == "tool_use":
                events.append(
                    ToolCall(
                        tool_call_id=content_block["id"],
                        tool_name=normalize_tool_name(content_block["name"]),
                        tool_args=content_block["input"],
                        timestamp=session_msg.timestamp,
                        uuid=session_msg.uuid,
                    )
                )

            elif content_block["type"] == "tool_result":
                result_content = content_block["content"]

                if isinstance(result_content, list):
                    text_parts = [item.get("text", "") for item in result_content if item.get("type") == "text"]
                    result_str = "\n".join(text_parts)
                else:
                    result_str = str(result_content)

                events.append(
                    ToolResult(
                        tool_call_id=content_block["tool_use_id"],
                        result_content=result_str,
                        is_error=content_block.get("is_error", False),
                        timestamp=session_msg.timestamp,
                        uuid=session_msg.uuid,
                    )
                )

    return events
