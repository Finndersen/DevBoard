"""Tests for ClaudeResponseParser with preamble and postamble handling."""

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

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.preamble is None

    def test_plain_json_with_preamble(self):
        """Test plain JSON with preamble text (no code block)."""
        text = """You're right - there's significant duplication between the task specification and implementation plan.

{"tool_name": "edit_task_specification", "arguments": {"edits": [{"find": "old text", "replace": "new text"}]}}"""

        parsed = ClaudeResponseParser.parse_message_content(text)

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

        parsed = ClaudeResponseParser.parse_message_content(text)

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

        parsed = ClaudeResponseParser.parse_message_content(text)

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

        parsed = ClaudeResponseParser.parse_message_content(text)

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

        parsed = ClaudeResponseParser.parse_message_content(text)

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

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.valid is False
        assert parsed.preamble == "I'll fix the issues now."
        assert parsed.validation_error is not None
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

        parsed = ClaudeResponseParser.parse_message_content(text)

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

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.preamble is None


class TestPostambleHandling:
    """Tests for postamble extraction in virtual tool calls."""

    def test_plain_json_with_postamble(self):
        """Test plain JSON with postamble text (no code block)."""
        text = """{"tool_name": "edit_task_specification", "arguments": {"edits": []}}

I'll update the implementation plan next."""

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.preamble is None
        assert parsed.postamble == "I'll update the implementation plan next."
        assert parsed.valid is True

    def test_plain_json_with_multiline_postamble(self):
        """Test plain JSON with multiline postamble (no code block)."""
        text = """{"tool_name": "edit_task_specification", "arguments": {"edits": []}}

This will consolidate the documents.

Let me know if you need any adjustments."""

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        expected_postamble = """This will consolidate the documents.

Let me know if you need any adjustments."""
        assert parsed.postamble == expected_postamble

    def test_code_block_json_with_postamble(self):
        """Test JSON in code block with postamble text."""
        text = """```json
{
  "tool_name": "edit_task_specification",
  "arguments": {
    "edits": []
  }
}
```

This should address all the duplication issues."""

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.preamble is None
        assert parsed.postamble == "This should address all the duplication issues."
        assert parsed.valid is True

    def test_preamble_and_postamble(self):
        """Test tool call with both preamble and postamble."""
        text = """Let me update the specification now.

```json
{
  "tool_name": "edit_task_specification",
  "arguments": {
    "edits": []
  }
}
```

I'll verify the changes afterwards."""

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.preamble == "Let me update the specification now."
        assert parsed.postamble == "I'll verify the changes afterwards."
        assert parsed.valid is True

    def test_preamble_and_postamble_plain_json(self):
        """Test plain JSON with both preamble and postamble (no code block)."""
        text = """I'll start by editing the specification.

{"tool_name": "edit_task_specification", "arguments": {"edits": []}}

Then we can proceed with testing."""

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.preamble == "I'll start by editing the specification."
        assert parsed.postamble == "Then we can proceed with testing."
        assert parsed.valid is True

    def test_invalid_tool_call_with_postamble(self):
        """Test invalid tool call structure with postamble."""
        text = """```json
{
  "tool_name": "edit_task_specification"
}
```

Let me know if you need changes."""

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.valid is False
        assert parsed.preamble is None
        assert parsed.postamble == "Let me know if you need changes."
        assert parsed.validation_error is not None
        assert "Invalid tool call format" in parsed.validation_error

    def test_invalid_tool_call_with_preamble_and_postamble(self):
        """Test invalid tool call with both preamble and postamble."""
        text = """I'll fix this now.

```json
{
  "tool_name": "edit_task_specification"
}
```

This might need a retry."""

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.valid is False
        assert parsed.preamble == "I'll fix this now."
        assert parsed.postamble == "This might need a retry."
        assert parsed.validation_error is not None
        assert "Invalid tool call format" in parsed.validation_error

    def test_empty_postamble_not_set(self):
        """Test that whitespace-only postamble is not set."""
        text = """```json
{
  "tool_name": "edit_task_specification",
  "arguments": {
    "edits": []
  }
}
```

        """

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.postamble is None


class TestEarlyExitOptimization:
    """Tests for the 'tool_name' early exit optimisation in parse_message_content()."""

    def test_plain_text_takes_early_exit(self):
        """Plain text without 'tool_name' should return TextResponse immediately."""
        text = "I've analyzed the task and here's my recommendation."

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text

    def test_code_block_without_tool_name_takes_early_exit(self):
        """Code block without 'tool_name' should return TextResponse via early exit."""
        text = "```python\ndef hello():\n    pass\n```"

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text

    def test_json_without_tool_name_takes_early_exit(self):
        """JSON object without 'tool_name' key should return TextResponse via early exit."""
        text = '{"key": "value", "count": 42}'

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text

    def test_tool_name_in_text_does_not_skip_detection(self):
        """Text containing 'tool_name' as JSON key should still be parsed as VirtualToolCall."""
        import json as _json

        text = _json.dumps({"tool_name": "edit_task_specification", "arguments": {}})

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "edit_task_specification"

    def test_tool_result_xml_still_parsed_when_tool_name_present(self):
        """Tool result XML (which contains 'tool_name=') should still be parsed correctly."""
        text = '<tool_call_result tool_name="my_tool" outcome="success">\nDone\n</tool_call_result>'

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolResult)
        assert parsed.tool_name == "my_tool"
        assert parsed.outcome == ToolCallOutcome.SUCCESS

    def test_preamble_with_tool_name_in_json_still_detected(self):
        """Message with preamble and 'tool_name' JSON key should still produce VirtualToolCall."""
        import json as _json

        tool_json = _json.dumps({"tool_name": "run_tests", "arguments": {"path": "."}})
        text = f"Running tests now.\n\n{tool_json}"

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolCall)
        assert parsed.tool_name == "run_tests"
        assert parsed.preamble == "Running tests now."

    def test_tool_name_substring_in_prose_is_safe_false_negative(self):
        """Text containing 'tool_name' as prose (not JSON/XML) falls through to TextResponse.

        The early exit is conservative: if 'tool_name' is present we do the full parse.
        A false negative (skipping early exit when we could have taken it) is harmless —
        the full parse still returns TextResponse when neither TOOL_RESULT_PATTERN nor
        _detect_virtual_tool_call() matches.
        """
        text = "The variable tool_name is used in the function signature."

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text


class TestTextResponseWithoutToolCall:
    """Tests for text responses that should not be parsed as tool calls."""

    def test_text_with_json_like_content(self):
        """Test text message containing JSON-like content but not a tool call."""
        text = 'The configuration should include {"key": "value"} in the settings.'

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text

    def test_plain_text_message(self):
        """Test plain text message without any JSON."""
        text = "I've analyzed the task and here's what I found..."

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text

    def test_text_with_code_block_non_json(self):
        """Test text with code block containing non-JSON content."""
        text = """Here's the implementation:

```python
def hello():
    print("Hello, world!")
```"""

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text

    def test_long_markdown_with_tool_name_in_explanatory_text(self):
        """Test that a long markdown response describing tool_name in code examples is not a false positive."""
        text = """The virtual tool system uses a JSON format to communicate tool calls. Here is an example:

```json
{"tool_name": "<tool_name>", "arguments": {...}}
```

When the agent wants to call a tool, it outputs this JSON. The backend parses the response
and extracts the tool name and arguments. If the response contains `"tool_name":` in an
explanatory context, the parser must not treat it as an actual tool call.

This is a detailed explanation of how the system works, with many closing braces: } } }
The above braces are just part of the explanation text."""

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text

    def test_placeholder_notation_not_detected_as_tool_call(self):
        """Test that placeholder JSON notation with {...} is not detected as a tool call."""
        text = '{"tool_name": "<tool_name>", "arguments": {...}}'

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, TextResponse)
        assert parsed.content == text


class TestToolResultParsing:
    """Tests for tool result XML marker parsing."""

    def test_success_tool_result(self):
        """Test parsing successful tool result."""
        text = '<tool_call_result tool_name="edit_task_specification" outcome="success">\nEdit completed successfully\n</tool_call_result>'

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolResult)
        assert parsed.tool_name == "edit_task_specification"
        assert parsed.outcome == ToolCallOutcome.SUCCESS
        assert parsed.content == "Edit completed successfully"
        assert parsed.successful is True

    def test_validation_error_tool_result(self):
        """Test parsing validation error tool result."""
        text = '<tool_call_result tool_name="edit_task_specification" outcome="validation_error">\nInvalid arguments provided\n</tool_call_result>'

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolResult)
        assert parsed.outcome == ToolCallOutcome.VALIDATION_ERROR
        assert parsed.successful is False

    def test_denied_tool_result(self):
        """Test parsing denied tool result."""
        text = '<tool_call_result tool_name="edit_task_specification" outcome="denied">\nUser denied the operation\n</tool_call_result>'

        parsed = ClaudeResponseParser.parse_message_content(text)

        assert isinstance(parsed, VirtualToolResult)
        assert parsed.outcome == ToolCallOutcome.DENIED
        assert parsed.successful is False

    def test_error_tool_result(self):
        """Test parsing error tool result."""
        text = '<tool_call_result tool_name="edit_task_specification" outcome="error">\nTool execution failed: file not found\n</tool_call_result>'

        parsed = ClaudeResponseParser.parse_message_content(text)

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

    def test_returns_none_for_malformed_json(self):
        """Test that malformed JSON is not detected as a tool call."""
        text = '{"tool_name": "test_tool", "arguments": {missing quote}}'

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert result is None

    def test_returns_none_for_malformed_json_with_preamble(self):
        """Test that malformed JSON with preamble is not detected as a tool call."""
        text = """Let me update the specification.

{"tool_name": "edit_task", "arguments": {missing: "quote"}}"""

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert result is None

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

    def test_tool_call_with_postamble(self):
        """Test tool call with postamble text."""
        text = """{"tool_name": "test_tool", "arguments": {}}

This will complete the task."""

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert isinstance(result, VirtualToolCall)
        assert result.tool_name == "test_tool"
        assert result.preamble is None
        assert result.postamble == "This will complete the task."
        assert result.valid is True

    def test_tool_call_with_preamble_and_postamble(self):
        """Test tool call with both preamble and postamble."""
        text = """Let me create the file now.

{"tool_name": "test_tool", "arguments": {}}

I'll run the tests afterwards."""

        result = ClaudeResponseParser._detect_virtual_tool_call(text)

        assert isinstance(result, VirtualToolCall)
        assert result.tool_name == "test_tool"
        assert result.preamble == "Let me create the file now."
        assert result.postamble == "I'll run the tests afterwards."
        assert result.valid is True
