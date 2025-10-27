"""Centralized message parser for Claude Code agent responses.

This module provides utilities for parsing and validating Claude Code agent
responses, including JSON extraction, XML marker detection, and response type
classification.
"""

import datetime
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from pydantic_core import ValidationError

from devboard.agents.events import ConversationEvent, ConversationMessage, MessageRole, ToolCall, ToolCallRequest


@dataclass
class TextResponse:
    """Response from Claude Code agent containing a text message."""

    content: str


class ToolCallOutcome(str, Enum):
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
    # Import here to avoid circular imports

    events: list[ConversationEvent] = []

    # Generate preamble message if present
    if tool_call.preamble:
        events.append(
            ConversationMessage(
                role=MessageRole.AGENT,
                text_content=tool_call.preamble,
                timestamp=timestamp,
            )
        )

    # Generate tool call event (request or regular call)
    if use_tool_call_request:
        events.append(
            ToolCallRequest(
                tool_call_id=tool_call.tool_name,  # For virtual tools, tool_name is the ID
                tool_name=tool_call.tool_name,
                tool_args=tool_call.arguments,
                timestamp=timestamp,
            )
        )
    else:
        events.append(
            ToolCall(
                tool_call_id=tool_call.tool_name,  # Use tool_name as ID for virtual tools
                tool_name=tool_call.tool_name,
                tool_args=tool_call.arguments,
                timestamp=timestamp,
            )
        )

    # Generate postamble message if present
    if tool_call.postamble:
        events.append(
            ConversationMessage(
                role=MessageRole.AGENT,
                text_content=tool_call.postamble,
                timestamp=timestamp,
            )
        )

    return events


class ClaudeResponseParser:
    """Parser for Claude Code agent responses with XML marker support."""

    # XML marker pattern - now includes outcome attribute
    TOOL_RESULT_PATTERN = re.compile(
        r'<tool_call_result\s+tool_name="([^"]+)"\s+outcome="([^"]+)">(.*?)</tool_call_result>',
        re.DOTALL,
    )

    # Tool call pattern with optional preamble and postamble
    # Captures:
    # - Group 1 (optional): Preamble text before the tool call
    # - Group 2: The JSON content (must contain "tool_name" field somewhere)
    # - Group 3 (optional): Postamble text after the tool call
    # This pattern looks for JSON objects in code blocks or plain text
    TOOL_CALL_PATTERN = re.compile(
        r"^(.*?)?"  # Optional preamble (non-greedy)
        r"(?:```(?:json)?\s*\n)?"  # Optional code block start (non-capturing)
        r'(\{.*?"tool_name":.*\})'  # JSON object containing "tool_name" field
        r"(?:\n```)?"  # Optional code block end (non-capturing)
        r"(.*?)$",  # Optional postamble (non-greedy)
        re.DOTALL,
    )

    @classmethod
    def _detect_virtual_tool_call(cls, text: str) -> VirtualToolCall | None:
        """Detect and parse a virtual tool call with optional preamble and postamble.

        Uses regex to match tool calls in various formats:
        - Plain JSON: {"tool_name": "...", "arguments": {...}}
        - JSON with preamble: Some text\n{"tool_name": ...}
        - JSON with postamble: {"tool_name": ...}\nSome text
        - JSON with preamble and postamble: Some text\n{"tool_name": ...}\nMore text
        - JSON in code block: ```json\n{"tool_name": ...}\n```
        - JSON in code block with preamble: Some text\n```json\n{"tool_name": ...}\n```
        - JSON in code block with postamble: ```json\n{"tool_name": ...}\n```\nSome text

        Args:
            text: Text potentially containing a tool call

        Returns:
            VirtualToolCall (valid or invalid) if JSON tool call detected, None otherwise
        """
        text = text.strip()

        # Try regex pattern first (handles all formats with preamble and postamble)
        match = cls.TOOL_CALL_PATTERN.match(text)
        if not match:
            # No match - not a tool call
            return None

        # Extract preamble if present
        preamble = stripped_text if (stripped_text := match.group(1).strip()) else None

        # Extract JSON content
        json_str = match.group(2).strip()

        # Extract postamble if present
        postamble = stripped_text if (stripped_text := match.group(3).strip()) else None
        try:
            json_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Malformed JSON in what appears to be a tool call - return invalid tool call
            return VirtualToolCall(
                tool_name="invalid_tool_call",
                arguments={},
                valid=False,
                validation_error=f"Malformed JSON in tool call: {str(e)}",
                preamble=preamble,
                postamble=postamble,
            )

        # Ensure we have a dict
        if not isinstance(json_data, dict):
            return VirtualToolCall(
                tool_name="invalid_tool_call",
                arguments={},
                valid=False,
                validation_error="Tool call JSON must be an object, not an array or primitive",
                preamble=preamble,
                postamble=postamble,
            )

        # Try to parse as ToolCall (validates tool_name and arguments structure)
        try:
            tool_call = VirtualToolCallSchema.model_validate(json_data)
            # Convert to VirtualToolCall with preamble and postamble
            return VirtualToolCall(
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                valid=True,
                preamble=preamble,
                postamble=postamble,
            )
        except ValidationError as e:
            # Return invalid tool call with preamble and postamble
            tool_name = json_data.get("tool_name")
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
