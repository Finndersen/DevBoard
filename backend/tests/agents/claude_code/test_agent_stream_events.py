"""Comprehensive tests for ClaudeCodeAgent.stream_events() method."""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolResultBlock, ToolUseBlock, UserMessage
from pydantic_ai import Tool

from devboard.agents.engines.claude_code.agent import ClaudeCodeAgent
from devboard.agents.events import MessageRole, TextMessage, ToolCall, ToolCallRequest, ToolResult
from devboard.agents.language_models import LanguageModel, LLMProvider, ModelType
from devboard.agents.roles.base import Role
from devboard.api.schemas.agent_conversation import ToolApprovalDecision, ToolApprovals


class MockRole(Role):
    """Mock role implementation for testing."""

    def __init__(self, tools: list[Tool] | None = None):
        self._test_tools = tools or []

    def get_system_prompt(self) -> str:
        return "Test system prompt"

    def get_tools(self) -> list[Tool]:
        return self._test_tools

    async def get_context_content(self) -> str:
        return "Test context content"


def create_mock_result_message(content: str, session_id: str = "test-session-123") -> ResultMessage:
    """Helper to create a ResultMessage for testing."""
    return ResultMessage(
        subtype="complete",
        duration_ms=1000,
        duration_api_ms=800,
        is_error=False,
        num_turns=1,
        session_id=session_id,
        total_cost_usd=0.001,
        result=content,
    )


def create_mock_assistant_message_with_text(content: str) -> AssistantMessage:
    """Helper to create an AssistantMessage with TextBlock for testing."""
    return AssistantMessage(
        content=[TextBlock(text=content)],
        model="claude-sonnet-4",
        parent_tool_use_id=None,
    )


def create_mock_text_stream(content: str, session_id: str = "test-session-123") -> list:
    """Helper to create a complete message stream for text content.

    This simulates the real Claude SDK streaming behavior where:
    1. An AssistantMessage with TextBlock is streamed first
    2. A ResultMessage with the same content is sent at the end

    Args:
        content: The text content to include in both messages
        session_id: Session ID for the ResultMessage

    Returns:
        List of messages [AssistantMessage, ResultMessage] to be yielded by mock
    """
    return [
        create_mock_assistant_message_with_text(content),
        create_mock_result_message(content, session_id=session_id),
    ]


def create_mock_tool_use_block(tool_name: str, tool_id: str, args: dict[str, Any]) -> ToolUseBlock:
    """Helper to create a ToolUseBlock for testing."""
    return ToolUseBlock(
        id=tool_id,
        name=tool_name,
        input=args,
    )


def setup_mock_client(mock_client_class, messages_to_yield):
    """Helper to set up a mock ClaudeClient that yields specified messages.

    Args:
        mock_client_class: The patched ClaudeClient class
        messages_to_yield: Single message or list of messages to yield from stream

    Returns:
        The mock client instance
    """
    mock_client = AsyncMock()

    # Ensure messages_to_yield is a list
    if not isinstance(messages_to_yield, list):
        messages_to_yield = [messages_to_yield]

    async def mock_stream(user_query):
        for message in messages_to_yield:
            yield message

    mock_client.stream = mock_stream
    mock_client_class.return_value = mock_client
    return mock_client


def setup_mock_client_with_callback(mock_client_class, stream_callback):
    """Helper to set up a mock ClaudeClient with a custom stream callback.

    Useful for tests that need to track call counts or implement conditional logic.

    Args:
        mock_client_class: The patched ClaudeClient class
        stream_callback: Async generator function to use as the stream method

    Returns:
        The mock client instance
    """
    mock_client = AsyncMock()
    mock_client.stream = stream_callback
    mock_client_class.return_value = mock_client
    return mock_client


@pytest.fixture
def mock_model() -> LanguageModel:
    """Create a mock language model."""
    return LanguageModel(
        provider=LLMProvider.ANTHROPIC,
        name="claude-sonnet-4",
        type=ModelType.REASONING,
        full_name="claude-sonnet-4-20250514",
    )


@pytest.fixture
def mock_virtual_tool() -> Tool:
    """Create a mock virtual tool (requires approval)."""

    def edit_document_fn(edits: list[dict[str, str]], reasoning: str = "") -> str:
        return "Edit successful"

    return Tool(function=edit_document_fn, name="edit_document", requires_approval=True)


@pytest.fixture
def mock_function_tool() -> Tool:
    """Create a mock function tool (no approval required)."""

    def search_code_fn(query: str, file_pattern: str = "*") -> str:
        return "Search results"

    return Tool(function=search_code_fn, name="search_code", requires_approval=False)


@pytest.fixture
def agent_with_virtual_tool(mock_model: LanguageModel, mock_virtual_tool: Tool) -> ClaudeCodeAgent:
    """Create an agent with a virtual tool."""
    role = MockRole(tools=[mock_virtual_tool])
    return ClaudeCodeAgent(role=role, model=mock_model)


@pytest.fixture
def agent_with_function_tool(mock_model: LanguageModel, mock_function_tool: Tool) -> ClaudeCodeAgent:
    """Create an agent with a function tool."""
    role = MockRole(tools=[mock_function_tool])
    return ClaudeCodeAgent(role=role, model=mock_model)


@pytest.fixture
def agent_with_both_tools(
    mock_model: LanguageModel, mock_virtual_tool: Tool, mock_function_tool: Tool
) -> ClaudeCodeAgent:
    """Create an agent with both virtual and function tools."""
    role = MockRole(tools=[mock_virtual_tool, mock_function_tool])
    return ClaudeCodeAgent(role=role, model=mock_model)


class TestStreamEventsTextResponse:
    """Tests for stream_events() with simple text responses."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_simple_text_response(self, mock_client_class, agent_with_virtual_tool):
        """Test streaming a simple text response."""
        messages = create_mock_text_stream("Hello, this is a text response!")
        setup_mock_client(mock_client_class, messages)

        # Stream events
        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Verify events
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.AGENT
        assert events[0].text_content == "Hello, this is a text response!"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_multiline_text_response(self, mock_client_class, agent_with_virtual_tool):
        """Test streaming a multiline text response."""
        multiline_text = "Line 1\nLine 2\nLine 3"
        messages = create_mock_text_stream(multiline_text)
        setup_mock_client(mock_client_class, messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        assert len(events) == 1
        assert events[0].text_content == multiline_text

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_session_id_captured_from_result(self, mock_client_class, agent_with_virtual_tool):
        """Test that session_id is captured from result message."""
        new_session_id = "new-session-456"
        messages = create_mock_text_stream("Response", session_id=new_session_id)
        setup_mock_client(mock_client_class, messages)

        # Agent starts without session_id
        assert agent_with_virtual_tool.session_id is None

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Session ID should now be set
        assert agent_with_virtual_tool.session_id == new_session_id


class TestStreamEventsVirtualToolCalls:
    """Tests for stream_events() with virtual tool calls."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_valid_virtual_tool_call(self, mock_client_class, agent_with_virtual_tool):
        """Test streaming a valid virtual tool call."""
        tool_call_json = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_document",
                "arguments": {"edits": [{"find": "old", "replace": "new"}], "reasoning": "Update text"},
            }
        )
        messages = create_mock_text_stream(tool_call_json)
        setup_mock_client(mock_client_class, messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Verify tool call request
        assert len(events) == 1
        assert isinstance(events[0], ToolCallRequest)
        assert events[0].tool_name == "edit_document"
        assert events[0].tool_args["edits"][0]["find"] == "old"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_virtual_tool_call_with_preamble(self, mock_client_class, agent_with_virtual_tool):
        """Test virtual tool call with preamble text."""
        # Preamble is text BEFORE the JSON, not a field inside it
        tool_call_with_preamble = "I'll edit the document now\n" + json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_document",
                "arguments": {"edits": [{"find": "old", "replace": "new"}]},
            }
        )
        messages = create_mock_text_stream(tool_call_with_preamble)
        setup_mock_client(mock_client_class, messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have both preamble message and tool call request
        assert len(events) == 2
        assert isinstance(events[0], TextMessage)
        assert events[0].text_content == "I'll edit the document now"
        assert isinstance(events[1], ToolCallRequest)
        assert events[1].tool_name == "edit_document"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_virtual_tool_call_with_postamble(self, mock_client_class, agent_with_virtual_tool):
        """Test virtual tool call with postamble text."""
        # Postamble is text AFTER the JSON
        tool_call_with_postamble = (
            json.dumps(
                {
                    "type": "tool_call",
                    "tool_name": "edit_document",
                    "arguments": {"edits": [{"find": "old", "replace": "new"}]},
                }
            )
            + "\nI'll verify the changes afterwards"
        )
        messages = create_mock_text_stream(tool_call_with_postamble)
        setup_mock_client(mock_client_class, messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have tool call request and postamble message
        assert len(events) == 2
        assert isinstance(events[0], ToolCallRequest)
        assert events[0].tool_name == "edit_document"
        assert isinstance(events[1], TextMessage)
        assert events[1].text_content == "I'll verify the changes afterwards"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_virtual_tool_call_with_preamble_and_postamble(self, mock_client_class, agent_with_virtual_tool):
        """Test virtual tool call with both preamble and postamble text."""
        tool_call_with_both = (
            "I'll edit the document now\n"
            + json.dumps(
                {
                    "type": "tool_call",
                    "tool_name": "edit_document",
                    "arguments": {"edits": [{"find": "old", "replace": "new"}]},
                }
            )
            + "\nThis should fix the issue"
        )
        messages = create_mock_text_stream(tool_call_with_both)
        setup_mock_client(mock_client_class, messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have preamble message, tool call request, and postamble message
        assert len(events) == 3
        assert isinstance(events[0], TextMessage)
        assert events[0].text_content == "I'll edit the document now"
        assert isinstance(events[1], ToolCallRequest)
        assert events[1].tool_name == "edit_document"
        assert isinstance(events[2], TextMessage)
        assert events[2].text_content == "This should fix the issue"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_unknown_virtual_tool_triggers_retry(self, mock_client_class, agent_with_virtual_tool):
        """Test that unknown virtual tool triggers retry and eventually raises error."""
        # First 4 attempts (initial + 3 retries) return unknown tool
        tool_call_json = json.dumps({"type": "tool_call", "tool_name": "unknown_tool", "arguments": {"param": "value"}})

        call_count = 0

        async def mock_stream(user_query):
            nonlocal call_count
            call_count += 1
            for message in create_mock_text_stream(tool_call_json):
                yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        # Should raise ValueError after max retries
        with pytest.raises(ValueError) as exc_info:
            events = []
            async for event in agent_with_virtual_tool.stream_events("Test prompt"):
                events.append(event)

        assert "Tool call validation failed after 3 attempts" in str(exc_info.value)
        # Should have called stream 4 times (initial + 3 retries)
        assert call_count == 4


class TestStreamEventsFunctionToolCalls:
    """Tests for stream_events() with function tool calls (handled by Claude)."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_function_tool_call_and_result(self, mock_client_class, agent_with_function_tool):
        """Test streaming function tool calls and results from Claude."""
        # Create tool use and result messages
        tool_use_block = create_mock_tool_use_block(
            tool_name="search_code", tool_id="tool-123", args={"query": "test", "file_pattern": "*.py"}
        )
        assistant_msg = AssistantMessage(
            content=[tool_use_block],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )

        tool_result_block = ToolResultBlock(tool_use_id="tool-123", content="Found 5 matches", is_error=False)
        user_msg = UserMessage(content=[tool_result_block])

        # Create text stream for final message
        final_messages = create_mock_text_stream("Here are the search results...")

        setup_mock_client(mock_client_class, [assistant_msg, user_msg] + final_messages)

        events = []
        async for event in agent_with_function_tool.stream_events("Search for test"):
            events.append(event)

        # Should have: ToolCall, ToolResult, and final message
        assert len(events) == 3
        assert isinstance(events[0], ToolCall)
        assert events[0].tool_name == "search_code"
        assert events[0].tool_call_id == "tool-123"

        assert isinstance(events[1], ToolResult)
        assert events[1].tool_call_id == "tool-123"
        assert events[1].result_content == "Found 5 matches"
        assert events[1].is_error is False

        assert isinstance(events[2], TextMessage)
        assert events[2].text_content == "Here are the search results..."


class TestStreamEventsToolApprovals:
    """Tests for stream_events() processing tool approvals."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    @patch.object(ClaudeCodeAgent, "_process_tool_approvals")
    async def test_tool_approval_success(self, mock_process_approvals, mock_client_class, agent_with_virtual_tool):
        """Test processing approved tool call."""
        # Set session_id (required for processing approvals)
        agent_with_virtual_tool.session_id = "session-123"

        # Mock tool approval processing
        mock_process_approvals.return_value = (
            '<tool_call_result tool_name="edit_document" outcome="success">\n'
            "Edit completed successfully\n"
            "</tool_call_result>"
        )

        # Mock client response after approval
        messages = create_mock_text_stream("The document has been updated.")
        setup_mock_client(mock_client_class, messages)

        # Create tool approvals
        approvals = ToolApprovals(approvals={"edit_document": ToolApprovalDecision(approved=True, feedback=None)})

        events = []
        async for event in agent_with_virtual_tool.stream_events(approvals):
            events.append(event)

        # Verify approval was processed
        mock_process_approvals.assert_called_once_with(approvals)

        # Verify response
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].text_content == "The document has been updated."

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    @patch.object(ClaudeCodeAgent, "_process_tool_approvals")
    async def test_tool_denial_with_feedback(self, mock_process_approvals, mock_client_class, agent_with_virtual_tool):
        """Test processing denied tool call with feedback."""
        agent_with_virtual_tool.session_id = "session-123"

        # Mock tool denial processing
        mock_process_approvals.return_value = (
            '<tool_call_result tool_name="edit_document" outcome="denied">\n'
            "Tool execution denied: The edit is not appropriate\n"
            "</tool_call_result>"
        )

        # Mock client response after denial
        messages = create_mock_text_stream("I understand. Let me try a different approach.")
        setup_mock_client(mock_client_class, messages)

        # Create tool approvals (denied)
        approvals = ToolApprovals(
            approvals={"edit_document": ToolApprovalDecision(approved=False, feedback="The edit is not appropriate")}
        )

        events = []
        async for event in agent_with_virtual_tool.stream_events(approvals):
            events.append(event)

        mock_process_approvals.assert_called_once_with(approvals)
        assert len(events) == 1
        assert "different approach" in events[0].text_content

    @pytest.mark.asyncio
    async def test_tool_approval_without_session_raises_error(self, agent_with_virtual_tool):
        """Test that processing approvals without session_id raises ValueError."""
        # No session_id set
        assert agent_with_virtual_tool.session_id is None

        approvals = ToolApprovals(approvals={"edit_document": ToolApprovalDecision(approved=True, feedback=None)})

        with pytest.raises(ValueError, match="session_id required when processing tool approvals"):
            events = []
            async for event in agent_with_virtual_tool.stream_events(approvals):
                events.append(event)


class TestStreamEventsRetryLogic:
    """Tests for stream_events() retry logic on validation errors."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_invalid_arguments_retry_then_success(self, mock_client_class, agent_with_virtual_tool):
        """Test that invalid arguments trigger retry, then succeed."""
        # First call: invalid arguments (missing required field)
        invalid_tool_call = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_document",
                "arguments": {"reasoning": "Missing edits field"},
            }
        )

        # Second call: valid arguments
        valid_tool_call = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_document",
                "arguments": {"edits": [{"find": "old", "replace": "new"}]},
            }
        )

        call_count = 0

        async def mock_stream(user_query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                for message in create_mock_text_stream(invalid_tool_call):
                    yield message
            else:
                # Check that error feedback was provided
                assert "ERROR: Invalid arguments" in user_query
                for message in create_mock_text_stream(valid_tool_call):
                    yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should succeed after retry
        assert call_count == 2
        assert len(events) == 1
        assert isinstance(events[0], ToolCallRequest)

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_max_retries_exceeded_raises_error(self, mock_client_class, agent_with_virtual_tool):
        """Test that exceeding max retries raises ValueError."""
        # Always return invalid tool call
        invalid_tool_call = json.dumps(
            {"type": "tool_call", "tool_name": "edit_document", "arguments": {"invalid": "args"}}
        )

        call_count = 0

        async def mock_stream(user_query):
            nonlocal call_count
            call_count += 1
            for message in create_mock_text_stream(invalid_tool_call):
                yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        with pytest.raises(ValueError) as exc_info:
            events = []
            async for event in agent_with_virtual_tool.stream_events("Test prompt"):
                events.append(event)

        assert "Tool call validation failed after 3 attempts" in str(exc_info.value)
        assert call_count == 4  # Initial + 3 retries


class TestStreamEventsEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_no_result_message_raises_error(self, mock_client_class, agent_with_virtual_tool):
        """Test that missing ResultMessage raises RuntimeError."""

        # Stream with no ResultMessage
        async def mock_stream(user_query):
            # Empty stream - no messages yielded
            return
            yield  # Make this an async generator

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        with pytest.raises(RuntimeError, match="No ResultMessage received from Claude SDK"):
            events = []
            async for event in agent_with_virtual_tool.stream_events("Test prompt"):
                events.append(event)

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_empty_result_content_raises_error(self, mock_client_class, agent_with_virtual_tool):
        """Test that empty result content produces empty message."""
        messages = create_mock_text_stream("")
        setup_mock_client(mock_client_class, messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should successfully create an empty message
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].text_content == ""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_multiple_messages_in_stream(self, mock_client_class, agent_with_both_tools):
        """Test handling multiple messages in a single stream."""
        # Create a complex stream with tool use
        tool_use = create_mock_tool_use_block("search_code", "tool-1", {"query": "test"})
        assistant_msg = AssistantMessage(content=[tool_use], model="claude-sonnet-4", parent_tool_use_id=None)

        tool_result = ToolResultBlock(tool_use_id="tool-1", content="Results found", is_error=False)
        user_msg = UserMessage(content=[tool_result])

        final_messages = create_mock_text_stream("Analysis complete")

        setup_mock_client(mock_client_class, [assistant_msg, user_msg] + final_messages)

        events = []
        async for event in agent_with_both_tools.stream_events("Analyze code"):
            events.append(event)

        # Should have tool call, tool result, and final message
        assert len(events) == 3
        assert isinstance(events[0], ToolCall)
        assert isinstance(events[1], ToolResult)
        assert isinstance(events[2], TextMessage)
