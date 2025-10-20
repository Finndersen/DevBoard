"""Centralized message parser for Claude Code agent responses.

This module provides utilities for parsing and validating Claude Code agent
responses, including JSON extraction, XML marker detection, and response type
classification.
"""

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from pydantic_core import ValidationError


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


class VirtualToolCall(BaseModel):
    """Represents a single virtual tool call request from Claude.

    This model handles both valid and invalid tool call attempts:
    - For valid calls: tool_name and arguments are properly populated, valid=True
    - For invalid calls: tool_name may be "invalid_tool_call", arguments may be empty, valid=False

    Note: tool_name serves as the tool_call_id since only one tool call
    is allowed at a time. The backend uses tool_name as the identifier.
    """

    tool_name: str = Field(description="Name of the tool to call")
    arguments: dict[str, Any] = Field(description="Arguments for the tool")
    valid: bool = Field(default=True, description="Whether the tool call passed structural validation")
    validation_error: str | None = Field(default=None, description="Validation error message if valid=False")


class VirtualToolRequests(BaseModel):
    """Container for virtual tool call requests."""

    calls: list[VirtualToolCall]


class ClaudeResponseParser:
    """Parser for Claude Code agent responses with XML marker support."""

    # XML marker pattern - now includes outcome attribute
    TOOL_RESULT_PATTERN = re.compile(
        r'<tool_call_result\s+tool_name="([^"]+)"\s+outcome="([^"]+)">(.*?)</tool_call_result>',
        re.DOTALL,
    )

    # JSON code block patterns
    JSON_CODE_BLOCK_PATTERN = re.compile(
        r"```(?:json)?\s*\n(.*?)\n```",
        re.DOTALL,
    )

    @classmethod
    def extract_json(cls, text: str) -> dict | None:
        """Extract JSON from text, supporting plain JSON and code blocks.

        Tries multiple strategies:
        1. Parse as plain JSON
        2. Extract from ```json...``` code block
        3. Extract from ```...``` generic code block

        Args:
            text: Text potentially containing JSON

        Returns:
            Parsed JSON dict if found and valid, None otherwise
        """
        text = text.strip()

        # Try plain JSON first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from code block
        match = cls.JSON_CODE_BLOCK_PATTERN.search(text)
        if match:
            code_content = match.group(1).strip()
            try:
                return json.loads(code_content)
            except json.JSONDecodeError:
                pass

        return None

    @classmethod
    def parse_message(cls, text: str) -> TextResponse | VirtualToolCall | VirtualToolResult:
        """Parse a message and return the appropriate message type.

        This is the unified parsing method that should be used throughout the codebase
        to consistently handle all message types. Detects and returns:
        - VirtualToolResult: XML-marked tool results (success, validation_error, or denied)
        - VirtualToolCall: JSON tool call requests (both valid and invalid)
        - TextMessage: Regular text messages

        Args:
            text: Message text to parse

        Returns:
            One of: TextMessage, VirtualToolCall (valid or invalid), or VirtualToolResult
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

        # Try to extract JSON for virtual tool calls
        json_data = cls.extract_json(text)

        # If no JSON or not a dict, treat as normal message
        if not json_data or not isinstance(json_data, dict):
            return TextResponse(content=text)

        # Try to validate as tool call - catch ValidationError and return invalid VirtualToolCall
        try:
            # VirtualToolCall.valid will be True if is validation succeeds,
            # even though the arguments may still be invalid for the particular tool
            return VirtualToolCall.model_validate(json_data)
        except ValidationError as e:
            # Extract tool_name from JSON if present, otherwise use generic name
            tool_name = json_data.get("tool_name")
            error_details = "\n".join([f"- {err['loc'][0]}: {err['msg']}" for err in e.errors()])
            return VirtualToolCall(
                tool_name=tool_name or "invalid_tool_call",
                arguments={},
                valid=False,
                validation_error=f"Invalid tool call format:\n{error_details}",
            )
