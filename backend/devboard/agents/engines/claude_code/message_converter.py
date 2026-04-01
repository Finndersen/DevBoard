"""Convert Claude SDK messages to ConversationEvents.

Pure functions that transform Claude SDK Message objects into the application's
ConversationEvent types. These handle AssistantMessage (text + tool use blocks)
and UserMessage (tool result blocks), including virtual tool call detection and validation.
"""

import datetime
from collections.abc import Generator

from claude_agent_sdk import (
    AssistantMessage,
    Message,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from pydantic import ValidationError

from devboard.agents.engines.claude_code.message_parser import (
    ClaudeResponseParser,
    TextResponse,
    VirtualToolCall,
    convert_virtual_tool_call_to_events,
)
from devboard.agents.engines.claude_code.utils import normalize_tool_name
from devboard.agents.engines.claude_code.virtual_tools import VirtualTool
from devboard.agents.events import (
    ConversationEvent,
    MessageRole,
    TextMessage,
    ThinkingEvent,
    ToolCall,
    ToolResult,
)


class InvalidVirtualToolCallError(Exception):
    """Exception raised when a virtual tool call validation fails.

    This exception is used to trigger retry logic in stream_events().
    """

    def __init__(self, tool_name: str, error_message: str):
        self.tool_name = tool_name
        self.error_message = error_message
        super().__init__(f"Invalid virtual tool call for '{tool_name}': {error_message}")


def convert_claude_message_to_events(
    message: Message,
    virtual_tools: dict[str, VirtualTool],
    model: str | None = None,
) -> Generator[ConversationEvent]:
    """Convert Claude SDK Message to ConversationEvent(s).

    Raises:
        InvalidVirtualToolCallError: If a virtual tool call validation fails
    """
    # Filter out subagent messages
    if isinstance(message, (AssistantMessage, UserMessage)) and message.parent_tool_use_id is not None:
        return

    timestamp = datetime.datetime.now(datetime.UTC)

    if isinstance(message, AssistantMessage):
        for content_block in message.content:
            if isinstance(content_block, ToolUseBlock):
                normalized_tool_name = normalize_tool_name(content_block.name)
                yield ToolCall(
                    tool_call_id=content_block.id,
                    tool_name=normalized_tool_name,
                    tool_args=content_block.input,
                    timestamp=timestamp,
                )
            elif isinstance(content_block, TextBlock):
                yield from parse_claude_message_text(content_block.text, virtual_tools, model=model)
            elif isinstance(content_block, ThinkingBlock):
                yield ThinkingEvent(thinking_text=content_block.thinking, timestamp=timestamp, uuid=None)
    elif isinstance(message, UserMessage):
        if isinstance(message.content, list):
            for content_block in message.content:
                if isinstance(content_block, ToolResultBlock):
                    if isinstance(content_block.content, list):
                        text_parts = []
                        for item in content_block.content:
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                        result_str = "\n".join(text_parts)
                    elif content_block.content is None:
                        result_str = ""
                    else:
                        result_str = str(content_block.content)

                    yield ToolResult(
                        tool_call_id=content_block.tool_use_id,
                        result_content=result_str,
                        is_error=content_block.is_error or False,
                        timestamp=timestamp,
                    )


def parse_claude_message_text(
    text_content: str,
    virtual_tools: dict[str, VirtualTool],
    model: str | None = None,
) -> list[ConversationEvent]:
    """Parse Claude response text and convert to conversation events.

    Raises:
        InvalidVirtualToolCallError: If tool call validation fails
    """
    timestamp = datetime.datetime.now(datetime.UTC)
    response_text = text_content.strip()

    if virtual_tools:
        tool_call_or_text = ClaudeResponseParser.parse_message_content(response_text)
    else:
        tool_call_or_text = TextResponse(content=response_text)

    if isinstance(tool_call_or_text, VirtualToolCall):
        validate_virtual_tool_call(tool_call_or_text, virtual_tools)

        return convert_virtual_tool_call_to_events(
            tool_call=tool_call_or_text,
            timestamp=timestamp,
            use_tool_call_request=True,
            model=model,
        )

    elif isinstance(tool_call_or_text, TextResponse):
        return [
            TextMessage(
                role=MessageRole.AGENT,
                text_content=tool_call_or_text.content,
                timestamp=timestamp,
                model=model,
            )
        ]
    else:
        raise ValueError(f"Expected VirtualToolCall or TextMessage from agent response, got {type(tool_call_or_text)}")


def validate_virtual_tool_call(
    tool_call: VirtualToolCall,
    virtual_tools: dict[str, VirtualTool],
) -> None:
    """Validate a virtual tool call response.

    Raises:
        InvalidVirtualToolCallError: If validation fails
    """
    tool_name = tool_call.tool_name

    if not tool_call.valid:
        error_msg = (
            f"ERROR: {tool_call.validation_error}\n\n"
            f"Expected format:\n"
            f'{{"tool_name": "<tool_name>", '
            f'"arguments": {{"arg1": [...], "arg2": "..."}}}}\n\n'
            f"Please correct these errors and try again."
        )
        raise InvalidVirtualToolCallError(
            tool_name=tool_name,
            error_message=error_msg,
        )

    virtual_tool = virtual_tools.get(tool_name)
    if not virtual_tool:
        available_tools = list(virtual_tools.keys()) if virtual_tools else []
        tools_list = ", ".join(available_tools) if available_tools else "none"
        error_msg = (
            f"ERROR: Unknown virtual tool '{tool_name}'.\n\n"
            f"Available virtual tools: {tools_list}\n\n"
            f"Please use one of the available virtual tools, or an appropriate normal tool call."
        )
        raise InvalidVirtualToolCallError(
            tool_name=tool_name,
            error_message=error_msg,
        )

    try:
        virtual_tool.validate_args(tool_call.arguments)
    except ValidationError as e:
        error_details = "\n".join([f"- {err['loc'][0]}: {err['msg']}" for err in e.errors()])
        error_msg = (
            f"ERROR: Invalid arguments for tool '{tool_name}'.\n\n"
            f"Validation errors:\n{error_details}\n\n"
            f"Please check the tool schema and provide valid arguments."
        )
        raise InvalidVirtualToolCallError(
            tool_name=tool_name,
            error_message=error_msg,
        ) from e
