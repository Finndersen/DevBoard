"""Centralized message parser for Claude Code agent responses.

This module provides utilities for parsing and validating Claude Code agent
responses, including JSON extraction, XML marker detection, and response type
classification.
"""

import datetime
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from pydantic import BaseModel, Field
from pydantic_core import ValidationError

from devboard.agents.engines.claude_code.utils import normalize_tool_name
from devboard.agents.events import ConversationEvent, MessageRole, TextMessage, ToolCall, ToolCallRequest


@dataclass
class TextResponse:
    """Response from Claude Code agent containing a text message."""

    content: str


class ToolCallOutcome(StrEnum):
    """Enum for tool call outcomes."""

    SUCCESS = "success"
    VALIDATION_ERROR = "validation_error"
    ERROR = "error"  # Tool execution failed (raised ToolCallError)
    DENIED = "denied"


class VirtualToolResult(BaseModel):
    """Tool execution result (both successful and failed executions).

    This represents the result after a tool call is processed - either
    successfully executed, denied, or failed validation.
    """

    tool_name: str
    content: str = Field(description="Result content or error message")
    outcome: ToolCallOutcome = Field(description="Outcome of the tool call")

    @property
    def successful(self) -> bool:
        """Whether the tool execution was successful."""
        return self.outcome == ToolCallOutcome.SUCCESS


class VirtualToolCallSchema(BaseModel):
    """Base tool call structure for JSON parsing.

    This represents the core JSON schema for a tool call:
    - tool_name: The name of the tool to invoke
    - arguments: The arguments dict to pass to the tool
    """

    tool_name: str = Field(description="Name of the tool to call")
    arguments: dict[str, Any] = Field(description="Arguments for the tool")


class VirtualToolCall(VirtualToolCallSchema):
    """Represents a single virtual tool call request from Claude.

    Extends ToolCall with additional metadata for the virtual tool calling workflow:
    - valid: Whether the tool call structure is valid
    - validation_error: Error message if validation failed
    - preamble: Optional text content before the tool call JSON
    - postamble: Optional text content after the tool call JSON

    This model handles both valid and invalid tool call attempts:
    - For valid calls: tool_name and arguments are properly populated, valid=True
    - For invalid calls: tool_name may be "invalid_tool_call", arguments may be empty, valid=False

    Note: tool_name serves as the tool_call_id since only one tool call
    is allowed at a time. The backend uses tool_name as the identifier.
    """

    valid: bool = Field(default=True, description="Whether the tool call passed structural validation")
    validation_error: str | None = Field(default=None, description="Validation error message if valid=False")
    preamble: str | None = Field(default=None, description="Text content before the tool call JSON")
    postamble: str | None = Field(default=None, description="Text content after the tool call JSON")


def convert_virtual_tool_call_to_events(
    tool_call: VirtualToolCall,
    timestamp: datetime.datetime,
    use_tool_call_request: bool = False,
) -> list[ConversationEvent]:
    """Convert a VirtualToolCall to a list of ConversationEvent instances.

    This helper function provides a consistent way to convert VirtualToolCall objects
    into conversation events with proper ordering:
    1. Preamble message (if present)
    2. Tool call or tool call request
    3. Postamble message (if present)

    Args:
        tool_call: The VirtualToolCall to convert
        timestamp: Timestamp to use for all generated events
        use_tool_call_request: If True, generates ToolCallRequest (for approval workflow),
                               otherwise generates ToolCall (for history/recording)

    Returns:
        List of ConversationEvent instances (ConversationMessage and ToolCall/ToolCallRequest)
    """
    events: list[ConversationEvent] = []

    # Normalize tool name to strip MCP prefix
    normalized_tool_name = normalize_tool_name(tool_call.tool_name)

    # Generate preamble message if present
    if tool_call.preamble:
        events.append(
            TextMessage(
                role=MessageRole.AGENT,
                text_content=tool_call.preamble,
                timestamp=timestamp,
            )
        )

    # Generate tool call event (request or regular call)
    if use_tool_call_request:
        events.append(
            ToolCallRequest(
                tool_call_id=normalized_tool_name,  # For virtual tools, tool_name is the ID
                tool_name=normalized_tool_name,
                tool_args=tool_call.arguments,
                timestamp=timestamp,
            )
        )
    else:
        events.append(
            ToolCall(
                tool_call_id=normalized_tool_name,  # Use tool_name as ID for virtual tools
                tool_name=normalized_tool_name,
                tool_args=tool_call.arguments,
                timestamp=timestamp,
            )
        )

    # Generate postamble message if present
    if tool_call.postamble:
        events.append(
            TextMessage(
                role=MessageRole.AGENT,
                text_content=tool_call.postamble,
                timestamp=timestamp,
            )
        )

    return events


def format_tool_result(tool_name: str, outcome: ToolCallOutcome, content: str) -> str:
    """Format a tool result message with XML markers."""
    return f'<tool_call_result tool_name="{tool_name}" outcome="{outcome.value}">\n{content}\n</tool_call_result>'


class ClaudeResponseParser:
    """Parser for Claude Code agent responses with XML marker support."""

    # XML marker pattern - now includes outcome attribute
    TOOL_RESULT_PATTERN = re.compile(
        r'<tool_call_result\s+tool_name="([^"]+)"\s+outcome="([^"]+)">(.*?)</tool_call_result>',
        re.DOTALL,
    )

    @classmethod
    def _detect_virtual_tool_call(cls, text: str) -> VirtualToolCall | None:
        """Detect and parse a virtual tool call with optional preamble and postamble.

        Uses json.JSONDecoder.raw_decode() for precise JSON extraction, correctly
        handling nested braces without over-consuming surrounding content.

        Supports:
        - Plain JSON: {"tool_name": "...", "arguments": {...}}
        - JSON with preamble: Some text\\n{"tool_name": ...}
        - JSON with postamble: {"tool_name": ...}\\nSome text
        - JSON in code block: ```json\\n{"tool_name": ...}\\n```
        - All combinations of the above

        Args:
            text: Text potentially containing a tool call

        Returns:
            VirtualToolCall (valid or invalid) if a JSON tool call is detected, None otherwise
        """
        text = text.strip()

        # Match optional code fence: preamble before fence, JSON inside, postamble after
        fence_pattern = re.compile(r"^(.*?)```(?:json)?\s*\n([\s\S]*?)\n```([\s\S]*)$", re.DOTALL)
        fence_match = fence_pattern.match(text)

        if fence_match:
            preamble_raw = fence_match.group(1).strip()
            json_region = fence_match.group(2)
            postamble_raw = fence_match.group(3).strip()
        else:
            preamble_raw = ""
            json_region = text
            postamble_raw = ""

        brace_pos = json_region.find("{")
        if brace_pos == -1:
            return None

        # raw_decode extracts exactly one JSON value starting at brace_pos,
        # correctly handling any nesting depth without over-consuming
        try:
            json_data, end_pos = json.JSONDecoder().raw_decode(json_region, brace_pos)
        except json.JSONDecodeError:
            return None

        if not isinstance(json_data, dict) or "tool_name" not in json_data:
            return None

        # Build preamble from text before '{' in json_region, plus any fence preamble
        pre_brace = json_region[:brace_pos].strip()
        if fence_match:
            preamble = "\n\n".join(filter(None, [preamble_raw, pre_brace])) or None
            postamble = postamble_raw or None
        else:
            preamble = pre_brace or None
            postamble = json_region[end_pos:].strip() or None

        try:
            tool_call = VirtualToolCallSchema.model_validate(json_data)
            return VirtualToolCall(
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                valid=True,
                preamble=preamble,
                postamble=postamble,
            )
        except ValidationError as e:
            tool_name = cast(str | None, json_data.get("tool_name"))
            error_details = "\n".join([f"- {err['loc'][0]}: {err['msg']}" for err in e.errors()])
            return VirtualToolCall(
                tool_name=tool_name or "invalid_tool_call",
                arguments={},
                valid=False,
                validation_error=f"Invalid tool call format:\n{error_details}",
                preamble=preamble,
                postamble=postamble,
            )

    @classmethod
    def parse_message_content(cls, text: str) -> TextResponse | VirtualToolCall | VirtualToolResult:
        """Parse a message and return the appropriate message type (Detecting virtual tool calls and responses)

        This is the unified parsing method that should be used throughout the codebase
        to consistently handle all message types. Detects and returns:
        - VirtualToolResult: XML-marked tool results (success, validation_error, or denied)
        - VirtualToolCall: JSON tool call requests (both valid and invalid, with optional preamble)
        - TextResponse: Regular text messages

        Args:
            text: Message text to parse

        Returns:
            One of: TextResponse, VirtualToolCall (valid or invalid), or VirtualToolResult
            Never raises exceptions - all errors create invalid VirtualToolCall instances
        """
        # Check for tool result XML marker first (takes precedence)
        tool_result_match = cls.TOOL_RESULT_PATTERN.search(text)
        if tool_result_match:
            tool_name = tool_result_match.group(1)
            outcome_str = tool_result_match.group(2)
            result_text = tool_result_match.group(3).strip()
            # Convert outcome string to enum value
            try:
                outcome = ToolCallOutcome(outcome_str)
            except ValueError:
                # If invalid outcome, default to validation_error
                outcome = ToolCallOutcome.VALIDATION_ERROR
            return VirtualToolResult(tool_name=tool_name, outcome=outcome, content=result_text)

        # Try to detect virtual tool call (with preamble)
        tool_call = cls._detect_virtual_tool_call(text)
        if tool_call:
            return tool_call

        # No tool call detected - treat as normal message
        return TextResponse(content=text)
