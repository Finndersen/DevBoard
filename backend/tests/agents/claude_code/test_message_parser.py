"""Tests for ClaudeResponseParser with preamble handling."""

import json

from devboard.agents.engines.claude_code.message_parser import (
    ClaudeResponseParser,
    TextResponse,
    ToolCallOutcome,
    VirtualToolCall,
    VirtualToolResult,
)


class TestPreambleHandling:
    """Tests for preamble extraction in virtual tool calls."""

    def test_plain_json_no_preamble(self):
        """Test plain JSON without preamble."""
        text = json.dumps({"tool_name": "edit_task_specification", "arguments": {"edits": []}})

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.preamble is None

    def test_plain_json_with_preamble(self):
        """Test plain JSON with preamble text (no code block)."""
        text = """You're right - there's significant duplication between the task specification and implementation plan.

{"tool_name": "edit_task_specification", "arguments": {"edits": [{"find": "old text", "replace": "new text"}]}}"""

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert (
            parsed.preamble
            == "You're right - there's significant duplication between the task specification and implementation plan."
        )
        assert parsed.valid is True

    def test_plain_json_with_multiline_preamble(self):
        """Test plain JSON with multiline preamble (no code block)."""
        text = """Let me consolidate and make both documents more concise.

First, I'll update the task specification to remove the duplication.

{ "tool_name": "edit_task_specification", "arguments": {"edits": []}}"""

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        expected_preamble = """Let me consolidate and make both documents more concise.

First, I'll update the task specification to remove the duplication."""
        assert parsed.preamble == expected_preamble

    def test_code_block_json_with_preamble(self):
        """Test JSON in code block with preamble text."""
        text = """You're right - there's significant duplication between the task specification and implementation plan.

```json
{
  "tool_name": "edit_task_specification",
  "arguments": {
    "edits": [
      {"find": "old text", "replace": "new text"}
    ]
  }
}
```"""

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert (
            parsed.preamble
            == "You're right - there's significant duplication between the task specification and implementation plan."
        )
        assert parsed.valid is True

    def test_code_block_json_without_preamble(self):
        """Test JSON in code block without preamble."""
        text = """```json
{
  "tool_name": "edit_task_specification",
  "arguments": {
    "edits": []
  }
}
```"""

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.preamble is None

    def test_generic_code_block_with_preamble(self):
        """Test JSON in generic code block with preamble."""
        text = """Let me update the specification.

```
{
  "tool_name": "edit_task_specification",
  "arguments": {
    "edits": []
  }
}
```"""

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.preamble == "Let me update the specification."

    def test_invalid_tool_call_with_preamble(self):
        """Test invalid tool call structure with preamble."""
        text = """I'll fix the issues now.

```json
{
  "tool_name": "edit_task_specification"
}
```"""

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.valid is False
        assert parsed.preamble == "I'll fix the issues now."
        assert "Invalid tool call format" in parsed.validation_error

    def test_multiline_preamble(self):
        """Test tool call with multiline preamble."""
        text = """Let me consolidate and make both documents more concise.

First, I'll update the task specification to remove the duplication.
Then we can update the implementation plan accordingly.

```json
{
  "tool_name": "edit_task_specification",
  "arguments": {
    "edits": []
  }
}
```"""

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        expected_preamble = """Let me consolidate and make both documents more concise.

First, I'll update the task specification to remove the duplication.
Then we can update the implementation plan accordingly."""
        assert parsed.preamble == expected_preamble

    def test_empty_preamble_not_set(self):
        """Test that whitespace-only preamble is not set."""
        text = """

```json
{
  "tool_name": "edit_task_specification",
  "arguments": {
    "edits": []
  }
}
```"""

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.preamble is None


class TestTextResponseWithoutToolCall:
    """Tests for text responses that should not be parsed as tool calls."""

    def test_text_with_json_like_content(self):
        """Test text message containing JSON-like content but not a tool call."""
        text = 'The configuration should include {"key": "value"} in the settings.'

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text

    def test_plain_text_message(self):
        """Test plain text message without any JSON."""
        text = "I've analyzed the task and here's what I found..."

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text

    def test_text_with_code_block_non_json(self):
        """Test text with code block containing non-JSON content."""
        text = """Here's the implementation:

```python
def hello():
    print("Hello, world!")
```"""

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text


class TestToolResultParsing:
    """Tests for tool result XML marker parsing."""

    def test_success_tool_result(self):
        """Test parsing successful tool result."""
        text = '<tool_call_result tool_name="edit_task_specification" outcome="success">\nEdit completed successfully\n</tool_call_result>'

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolResult)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.outcome == ToolCallOutcome.SUCCESS
        assert parsed.content == "Edit completed successfully"
        assert parsed.successful is True

    def test_validation_error_tool_result(self):
        """Test parsing validation error tool result."""
        text = '<tool_call_result tool_name="edit_task_specification" outcome="validation_error">\nInvalid arguments provided\n</tool_call_result>'

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolResult)
        assert parsed.outcome == ToolCallOutcome.VALIDATION_ERROR
        assert parsed.successful is False

    def test_denied_tool_result(self):
        """Test parsing denied tool result."""
        text = '<tool_call_result tool_name="edit_task_specification" outcome="denied">\nUser denied the operation\n</tool_call_result>'

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolResult)
        assert parsed.outcome == ToolCallOutcome.DENIED
        assert parsed.successful is False

    def test_error_tool_result(self):
        """Test parsing error tool result."""
        text = '<tool_call_result tool_name="edit_task_specification" outcome="error">\nTool execution failed: file not found\n</tool_call_result>'

        parsed = ClaudeResponseParser.parse_message(text)

        assert isinstance(parsed, VirtualToolResult)
        assert parsed.outcome == ToolCallOutcome.ERROR
        assert parsed.successful is False


class TestDetectVirtualToolCall:
    """Tests for _detect_virtual_tool_call internal method."""

    def test_returns_none_for_non_json(self):
        """Test that non-JSON text returns None."""
        result = ClaudeResponseParser._detect_virtual_tool_call("Just plain text")

        assert result is None

    def test_returns_none_for_json_array(self):
        """Test that JSON array returns None."""
        result = ClaudeResponseParser._detect_virtual_tool_call('["array", "values"]')

        assert result is None

    def test_returns_tool_call_for_valid_json_object(self):
        """Test that valid tool call JSON returns VirtualToolCall."""
        text = json.dumps({"tool_name": "test_tool", "arguments": {}})

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert isinstance(result, VirtualToolCall)
        assert result.tool_name == "test_tool"
        assert result.valid is True

    def test_returns_none_for_json_without_tool_name(self):
        """Test that JSON object without tool_name field returns None."""
        text = json.dumps({"some_field": "value"})

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        # JSON without tool_name is not recognized as a tool call
        assert result is None

    def test_returns_invalid_tool_call_for_invalid_structure(self):
        """Test that invalid tool call structure returns invalid VirtualToolCall."""
        text = json.dumps({"tool_name": "test_tool"})  # Missing arguments field

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert isinstance(result, VirtualToolCall)
        assert result.valid is False
        assert result.validation_error is not None

    def test_returns_invalid_tool_call_for_malformed_json(self):
        """Test that malformed JSON in a tool call attempt returns invalid VirtualToolCall."""
        text = '{"tool_name": "test_tool", "arguments": {missing quote}}'

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert isinstance(result, VirtualToolCall)
        assert result.tool_name == "invalid_tool_call"
        assert result.valid is False
        assert "Malformed JSON" in result.validation_error

    def test_returns_invalid_tool_call_for_malformed_json_with_preamble(self):
        """Test that malformed JSON with preamble returns invalid VirtualToolCall with preamble."""
        text = """Let me update the specification.

{"tool_name": "edit_task", "arguments": {missing: "quote"}}"""

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert isinstance(result, VirtualToolCall)
        assert result.tool_name == "invalid_tool_call"
        assert result.valid is False
        assert result.preamble == "Let me update the specification."
        assert "Malformed JSON" in result.validation_error

    def test_returns_invalid_tool_call_for_json_array_in_tool_call_format(self):
        """Test that JSON array in tool call format returns invalid VirtualToolCall."""
        # If regex somehow matches an array, it should be rejected
        text = '["tool_name", "test"]'

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        # Should return None since regex won't match arrays
        assert result is None

    def test_complex_nested_tool_call(self):
        """Test parsing complex nested tool call structure."""
        text = """I'll make these changes now.

{
  "tool_name": "edit_document",
  "arguments": {
    "edits": [
      {
        "find": "old text with \\"quotes\\" and newlines\\n",
        "replace": "new text"
      },
      {
        "find": "another section",
        "replace": "updated section"
      }
    ],
    "reasoning": "Making multiple edits"
  }
}"""

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert isinstance(result, VirtualToolCall)
        assert result.tool_name == "edit_document"
        assert result.preamble == "I'll make these changes now."
        assert result.valid is True
        assert len(result.arguments["edits"]) == 2

    def test_tool_call_with_special_characters_in_preamble(self):
        """Test tool call with special characters and formatting in preamble."""
        text = """You're right - there's *significant* duplication! Let's fix it...

{"tool_name": "test_tool", "arguments": {}}"""

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert isinstance(result, VirtualToolCall)
        assert result.preamble == "You're right - there's *significant* duplication! Let's fix it..."
        assert result.valid is True

    def test_tool_call_in_code_block_with_complex_structure(self):
        """Test tool call in code block with very large, complex arguments."""
        text = """Here's the implementation:

```json
{
  "tool_name": "create_file",
  "arguments": {
    "path": "/path/to/file.py",
    "content": "def foo():\\n    pass\\n",
    "metadata": {
      "author": "test",
      "nested": {
        "deeply": {
          "nested": "value"
        }
      }
    }
  }
}
```"""

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert isinstance(result, VirtualToolCall)
        assert result.tool_name == "create_file"
        assert result.preamble == "Here's the implementation:"
        assert result.valid is True
        assert "nested" in result.arguments["metadata"]
