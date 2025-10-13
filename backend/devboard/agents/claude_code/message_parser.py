"""Centralized message parser for Claude Code agent responses.

This module provides utilities for parsing and validating Claude Code agent
responses, including JSON extraction, XML marker detection, and response type
classification.
"""

import json
import logging
import re
from enum import StrEnum

from pydantic import ValidationError

from devboard.agents.claude_code.virtual_tools import VirtualToolCall

logger = logging.getLogger(__name__)


class ClaudeMessageType(StrEnum):
    """Types of messages that can appear in Claude Code conversations."""

    MESSAGE = "message"  # Normal conversational message
    TOOL_CALL = "tool_call"  # Valid virtual tool call request
    INVALID_TOOL_CALL = "invalid_tool_call"  # Invalid virtual tool call (validation failed)
    VALIDATION_ERROR = "validation_error"  # Validation error response to agent after invalid tool call
    TOOL_RESULT = "tool_result"  # Tool execution result


class ClaudeResponseParser:
    """Parser for Claude Code agent responses with XML marker support."""

    # XML marker patterns
    VALIDATION_ERROR_PATTERN = re.compile(
        r"<validation_error>(.*?)</validation_error>",
        re.DOTALL,
    )
    TOOL_RESULT_PATTERN = re.compile(
        r'<tool_call_result\s+tool_name="([^"]+)">(.*?)</tool_call_result>',
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
    def detect_message_type(cls, text: str) -> ClaudeMessageType:
        """Detect the type of message based on content and markers.

        Args:
            text: Message text to analyze

        Returns:
            MessageType enum value
        """
        # Check for XML markers first
        if cls.VALIDATION_ERROR_PATTERN.search(text):
            return ClaudeMessageType.VALIDATION_ERROR

        if cls.TOOL_RESULT_PATTERN.search(text):
            return ClaudeMessageType.TOOL_RESULT

        # Use parse_message to detect tool calls
        try:
            parsed = cls.parse_message(text)
            if isinstance(parsed, VirtualToolCall):
                return ClaudeMessageType.TOOL_CALL
        except ValidationError:
            # JSON that fails tool call validation
            return ClaudeMessageType.INVALID_TOOL_CALL

        # Default to normal message
        return ClaudeMessageType.MESSAGE

    @classmethod
    def parse_message(cls, text: str) -> str | VirtualToolCall:
        """Parse a message and return either the text content or a VirtualToolCall.

        This is the unified parsing method that should be used throughout the codebase
        to consistently handle both regular messages and tool calls.

        JSON objects in the message are assumed to be tool calls and will be validated.
        If validation fails, a ValidationError is raised so the agent can retry.

        Args:
            text: Message text to parse

        Returns:
            Either the original text (for normal messages) or a VirtualToolCall
            (for valid tool call messages)

        Raises:
            ValidationError: If JSON object is present but fails VirtualToolCall validation.
                           This allows the agent to provide feedback and retry.
        """
        # Try to extract JSON
        json_data = cls.extract_json(text)

        # If no JSON or not a dict, treat as normal message
        if not json_data or not isinstance(json_data, dict):
            return text

        # Try to validate as tool call - let ValidationError propagate for retry handling
        # JSON objects should be treated as tool calls and validated
        return VirtualToolCall.model_validate(json_data)

    @classmethod
    def is_validation_error(cls, text: str) -> bool:
        """Check if text contains a validation error marker.

        Args:
            text: Message text to check

        Returns:
            True if validation error marker found
        """
        return bool(cls.VALIDATION_ERROR_PATTERN.search(text))

    @classmethod
    def is_tool_result(cls, text: str) -> bool:
        """Check if text contains a tool result marker.

        Args:
            text: Message text to check

        Returns:
            True if tool result marker found
        """
        return bool(cls.TOOL_RESULT_PATTERN.search(text))

    @classmethod
    def extract_tool_result_info(cls, text: str) -> tuple[str, str] | None:
        """Extract tool name and result from a tool result message.

        Args:
            text: Tool result message text

        Returns:
            Tuple of (tool_name, result_text) if found, None otherwise
        """
        match = cls.TOOL_RESULT_PATTERN.search(text)
        if match:
            tool_name = match.group(1)
            result_text = match.group(2).strip()
            return (tool_name, result_text)
        return None
