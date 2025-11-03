"""Tests for BaseClaudeAgent validation and retry logic."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock
from pydantic_ai import Tool

from devboard.agents.engines.claude_code.agent import (
    ClaudeCodeAgent,
    InvalidVirtualToolCallError,
)
from devboard.agents.events import ConversationMessage, MessageRole, ToolCallRequest
from devboard.agents.language_models import LanguageModel, LLMProvider, ModelType
from devboard.agents.roles.base import Role


def create_mock_result(text_content: str, session_id: str = "test-session") -> ResultMessage:
    """Helper to create a ResultMessage for testing."""
    mock_result_message = Mock(spec=ResultMessage)
    mock_result_message.session_id = session_id
    mock_result_message.result = text_content  # The text content is in the result attribute
    return mock_result_message


class MockRole(Role):
    """Mock role implementation for testing."""

    def __init__(self, tools=None):
        self._test_tools = tools or []

    def get_system_prompt(self) -> str:
        return "Test agent role description\n\nTest state context"

    def get_tools(self) -> list[Tool]:
        return self._test_tools

    async def get_context_content(self) -> str:
        return "Test context"


@pytest.fixture
def mock_edit_tool():
    """Create a mock PydanticAI Tool that requires approval."""

    def edit_document_fn(edits: list, reasoning: str = "") -> str:
        return "Edit successful"

    tool = Tool(function=edit_document_fn, name="edit_task_specification", requires_approval=True)
    return tool


@pytest.fixture
def test_agent(mock_edit_tool):
    """Create a test agent with a mock tool."""
    model = LanguageModel(
        provider=LLMProvider.ANTHROPIC,
        name="claude-sonnet-4",
        type=ModelType.REASONING,
        full_name="claude-sonnet-4-20250514",
    )
    role = MockRole(tools=[mock_edit_tool])
    return ClaudeCodeAgent(role=role, model=model)


class TestValidMessageResponse:
    """Tests for valid message responses."""

    def test_parse_valid_message_response(self, test_agent):
        """Test parsing a plain text message response."""
        text_content = "Hello, world!"

        response = test_agent._parse_claude_message_text(text_content)

        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ConversationMessage)
        assert response[0].role == MessageRole.AGENT
        assert response[0].text_content == "Hello, world!"


class TestValidToolCallResponse:
    """Tests for valid tool call responses."""

    def test_parse_valid_tool_call_response(self, test_agent):
        """Test parsing a valid tool call response."""
        result = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_task_specification",
                "arguments": {
                    "edits": [{"find": "old text", "replace": "new text"}],
                    "reasoning": "Test reasoning",
                },
            }
        )

        response = test_agent._parse_claude_message_text(result)

        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ToolCallRequest)
        assert response[0].tool_name == "edit_task_specification"
        assert response[0].tool_args["edits"][0]["find"] == "old text"


class TestInvalidJSONResponse:
    """Tests for invalid JSON responses - now treated as normal messages."""

    def test_invalid_json_treated_as_message(self, test_agent):
        """Test that non-JSON responses are treated as normal messages (no retry)."""
        text_content = "This is not JSON at all"

        response = test_agent._parse_claude_message_text(text_content)

        # Non-JSON is now treated as a normal text message
        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ConversationMessage)
        assert response[0].text_content == "This is not JSON at all"

    def test_plain_text_message_no_validation(self, test_agent):
        """Test that plain text messages work without JSON format."""
        text_content = "Hello! I've analyzed the task and here's what I found..."

        response = test_agent._parse_claude_message_text(text_content)

        # Plain text should work fine as normal message
        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ConversationMessage)
        assert "Hello! I've analyzed" in response[0].text_content


class TestInvalidResponseStructure:
    """Tests for JSON structures that trigger validation and retry."""

    def test_json_array_treated_as_message(self, test_agent):
        """Test that JSON array (not object) is treated as normal message."""
        text_content = '["array", "not", "object"]'

        response = test_agent._parse_claude_message_text(text_content)

        # JSON array should be treated as plain text message
        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ConversationMessage)
        assert response[0].text_content == '["array", "not", "object"]'

    def test_json_object_without_tool_fields_treated_as_message(self, test_agent):
        """Test that JSON object without tool_name field is treated as plain text message."""
        text_content = '{"content": "Hello", "no_tool_fields": true}'

        response = test_agent._parse_claude_message_text(text_content)

        # JSON without tool_name is treated as plain text message (no retry)
        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ConversationMessage)
        assert response[0].text_content == '{"content": "Hello", "no_tool_fields": true}'


class TestInvalidMessageFormat:
    """Tests for JSON objects that fail validation."""

    def test_json_object_without_tool_name_treated_as_message(self, test_agent):
        """Test that JSON object without tool_name is treated as plain text message."""
        text_content = '{"type": "message"}'

        response = test_agent._parse_claude_message_text(text_content)

        # JSON without tool_name is treated as plain text message (no validation/retry)
        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ConversationMessage)
        assert response[0].text_content == '{"type": "message"}'

    def test_message_with_content_works(self, test_agent):
        """Test that plain text message works correctly."""
        text_content = "Test message"

        response = test_agent._parse_claude_message_text(text_content)

        # Should return full text
        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ConversationMessage)
        assert response[0].text_content == "Test message"


class TestInvalidToolCallFormat:
    """Tests for invalid tool call format validation."""

    def test_tool_call_missing_tool_name_treated_as_message(self, test_agent):
        """Test that JSON with arguments but no tool_name is treated as plain text message."""
        text_content = '{"arguments": {}}'

        response = test_agent._parse_claude_message_text(text_content)

        # JSON without tool_name is treated as plain text message (no validation/retry)
        assert isinstance(response, list)
        assert len(response) == 1
        assert isinstance(response[0], ConversationMessage)
        assert response[0].text_content == '{"arguments": {}}'

    def test_tool_call_missing_arguments_raises_validation_error(self, test_agent):
        """Test that JSON with tool_name but no arguments raises validation error."""
        text_content = '{"tool_name": "edit_task_specification"}'

        # Should raise InvalidVirtualToolCallError
        with pytest.raises(InvalidVirtualToolCallError) as exc_info:
            test_agent._parse_claude_message_text(text_content)

        assert "Invalid tool call format" in exc_info.value.error_message
        assert exc_info.value.tool_name == "edit_task_specification"

    def test_tool_call_invalid_structure_raises_validation_error(self, test_agent):
        """Test that tool call with invalid structure raises validation error."""
        # Tool call detected (has tool_name and arguments) but structure is invalid
        text_content = '{"tool_name": "edit_task_specification", "arguments": "not a dict"}'

        # Should raise InvalidVirtualToolCallError
        with pytest.raises(InvalidVirtualToolCallError) as exc_info:
            test_agent._parse_claude_message_text(text_content)

        assert "Invalid tool call format" in exc_info.value.error_message
        assert exc_info.value.tool_name == "edit_task_specification"

    def test_tool_call_validation_error_raised(self, test_agent):
        """Test that tool call validation raises InvalidVirtualToolCallError."""
        text_content = '{"tool_name": "edit_task_specification", "arguments": "not a dict"}'

        # _parse_response() should raise InvalidVirtualToolCallError (not ValueError)
        # stream_events() catches this and retries, raising ValueError after max attempts
        with pytest.raises(InvalidVirtualToolCallError) as exc_info:
            test_agent._parse_claude_message_text(text_content)

        assert "Invalid tool call format" in exc_info.value.error_message


class TestUnknownTool:
    """Tests for unknown tool validation."""

    def test_unknown_tool_raises_validation_error(self, test_agent):
        """Test that unknown tool name raises validation error with available tools list."""
        text_content = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "nonexistent_tool",
                "arguments": {},
            }
        )

        # Should raise InvalidVirtualToolCallError
        with pytest.raises(InvalidVirtualToolCallError) as exc_info:
            test_agent._parse_claude_message_text(text_content)

        assert "Unknown virtual tool 'nonexistent_tool'" in exc_info.value.error_message
        assert "Available virtual tools:" in exc_info.value.error_message
        assert "edit_task_specification" in exc_info.value.error_message
        assert exc_info.value.tool_name == "nonexistent_tool"

    def test_unknown_tool_validation_error(self, test_agent):
        """Test that unknown tool raises validation error."""
        text_content = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "nonexistent_tool",
                "arguments": {},
            }
        )

        # _parse_response() should raise InvalidVirtualToolCallError
        with pytest.raises(InvalidVirtualToolCallError) as exc_info:
            test_agent._parse_claude_message_text(text_content)

        assert "Unknown virtual tool" in exc_info.value.error_message


class TestInvalidToolArguments:
    """Tests for invalid tool argument validation."""

    def test_invalid_tool_arguments_raise_validation_error(self, test_agent):
        """Test that invalid tool arguments raise validation error with error details."""
        text_content = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_task_specification",
                "arguments": {
                    # Missing required 'edits' field
                    "reasoning": "Test reasoning",
                },
            }
        )

        # Should raise InvalidVirtualToolCallError
        with pytest.raises(InvalidVirtualToolCallError) as exc_info:
            test_agent._parse_claude_message_text(text_content)

        assert "Invalid arguments for tool 'edit_task_specification'" in exc_info.value.error_message
        assert "Validation errors:" in exc_info.value.error_message
        assert exc_info.value.tool_name == "edit_task_specification"

    def test_wrong_type_arguments_raise_validation_error(self, test_agent):
        """Test that arguments with wrong types raise validation error."""
        text_content = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_task_specification",
                "arguments": {
                    "edits": "not a list",  # Should be a list
                    "reasoning": "Test reasoning",
                },
            }
        )

        # Should raise InvalidVirtualToolCallError
        with pytest.raises(InvalidVirtualToolCallError) as exc_info:
            test_agent._parse_claude_message_text(text_content)

        assert "Invalid arguments for tool 'edit_task_specification'" in exc_info.value.error_message
        assert "Validation errors:" in exc_info.value.error_message
        assert exc_info.value.tool_name == "edit_task_specification"

    def test_invalid_arguments_validation_error(self, test_agent):
        """Test that invalid arguments raise validation error."""
        text_content = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_task_specification",
                "arguments": {
                    "edits": "not a list",
                },
            }
        )

        # _parse_response() should raise InvalidVirtualToolCallError
        with pytest.raises(InvalidVirtualToolCallError) as exc_info:
            test_agent._parse_claude_message_text(text_content)

        assert "Invalid arguments" in exc_info.value.error_message


class TestRetryMechanism:
    """Tests for the retry mechanism."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_stream_events_yields_messages(self, mock_client_class, test_agent):
        """Test that stream_events() properly yields conversation messages."""
        # Create proper message stream with AssistantMessage and ResultMessage
        text_content = "Success"
        assistant_msg = AssistantMessage(
            content=[TextBlock(text=text_content)],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )
        result_msg = create_mock_result(text_content)

        # Create mock client instance with stream method
        mock_client = MagicMock()

        async def mock_stream(user_query):
            yield assistant_msg
            yield result_msg

        mock_client.stream = mock_stream
        mock_client_class.return_value = mock_client

        # Call stream_events
        events = []
        async for event in test_agent.stream_events(
            prompt_or_approvals="Test message",
        ):
            events.append(event)

        # Verify response is valid - should be a ConversationMessage
        assert len(events) == 1
        assert isinstance(events[0], ConversationMessage)
        assert events[0].role == MessageRole.AGENT
        assert events[0].text_content == "Success"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_run_creates_new_client_each_time(self, mock_client_class, test_agent):
        """Test that run() creates a new client on each call (for fresh system prompt)."""
        # Create mock messages
        text_content = "Success"
        assistant_msg = AssistantMessage(
            content=[TextBlock(text=text_content)],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )
        result_msg = create_mock_result(text_content)

        # Create mock client instance with stream method
        mock_client = MagicMock()

        async def mock_stream(user_query):
            yield assistant_msg
            yield result_msg

        mock_client.stream = mock_stream
        mock_client_class.return_value = mock_client

        # Call run twice (using new parameter name)
        await test_agent.run(prompt_or_approvals="Message 1")
        await test_agent.run(prompt_or_approvals="Message 2")

        # Verify client was created twice
        assert mock_client_class.call_count == 2
