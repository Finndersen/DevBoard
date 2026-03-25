"""Comprehensive tests for ClaudeCodeAgent.stream_events() method."""

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from pydantic_ai import Tool

from devboard.agents.engines.claude_code.agent import ClaudeCodeAgent, _should_retry_error_result
from devboard.agents.engines.claude_code.session import AssistantSessionMessage
from devboard.agents.events import MessageRole, TextMessage, ThinkingEvent, ToolCall, ToolCallRequest, ToolResult
from devboard.agents.language_models import LLMProvider, ModelType
from devboard.agents.roles.base import AgentRole
from devboard.api.schemas.agent_conversation import ToolApprovalDecision, ToolApprovals
from devboard.db.models.language_model import LanguageModelDB


class MockAgentRole(AgentRole):
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
        SystemMessage(subtype="session_start", data={"session_id": session_id}),
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

    async def mock_stream(user_query, **kwargs):
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


def create_mock_session_message_with_tool_call(tool_call_json: str) -> AssistantSessionMessage:
    """Helper to create an AssistantSessionMessage containing a virtual tool call."""
    return AssistantSessionMessage(
        uuid="test-uuid",
        timestamp=datetime.now(),
        line_num=1,
        is_sidechain=False,
        content=[{"type": "text", "text": tool_call_json}],
    )


@pytest.fixture
def mock_model() -> LanguageModelDB:
    """Create a mock language model."""
    return LanguageModelDB(
        provider=LLMProvider.ANTHROPIC,
        name="claude-sonnet-4",
        model_type=ModelType.STANDARD,
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
def agent_with_virtual_tool(mock_model: LanguageModelDB, mock_virtual_tool: Tool) -> ClaudeCodeAgent:
    """Create an agent with a virtual tool."""
    role = MockAgentRole(tools=[mock_virtual_tool])
    return ClaudeCodeAgent(role=role, model=mock_model)


@pytest.fixture
def agent_with_function_tool(mock_model: LanguageModelDB, mock_function_tool: Tool) -> ClaudeCodeAgent:
    """Create an agent with a function tool."""
    role = MockAgentRole(tools=[mock_function_tool])
    return ClaudeCodeAgent(role=role, model=mock_model)


@pytest.fixture
def agent_with_both_tools(
    mock_model: LanguageModelDB, mock_virtual_tool: Tool, mock_function_tool: Tool
) -> ClaudeCodeAgent:
    """Create an agent with both virtual and function tools."""
    role = MockAgentRole(tools=[mock_virtual_tool, mock_function_tool])
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

        async def mock_stream(user_query, **kwargs):
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
    @patch("devboard.agents.engines.claude_code.agent.ClaudeCodeSessionService")
    async def test_tool_approval_success(self, mock_session_service_class, mock_client_class, agent_with_virtual_tool):
        """Test processing approved tool call."""
        # Set session_id (required for processing approvals)
        agent_with_virtual_tool.session_id = "session-123"

        # Create mock session message with virtual tool call
        tool_call_json = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_document",
                "arguments": {"edits": [{"find": "old", "replace": "new"}], "reasoning": "Update text"},
            }
        )

        # Mock session service to return a message with tool call
        mock_session_service = mock_session_service_class.return_value
        mock_session_message = create_mock_session_message_with_tool_call(tool_call_json)
        mock_session_service.get_last_session_message.return_value = mock_session_message

        # Mock client response after approval
        messages = create_mock_text_stream("The document has been updated.")
        setup_mock_client(mock_client_class, messages)

        # Create tool approvals
        approvals = ToolApprovals(approvals={"edit_document": ToolApprovalDecision(approved=True, feedback=None)})

        events = []
        async for event in agent_with_virtual_tool.stream_events(approvals):
            events.append(event)

        # Verify session service was called
        mock_session_service.get_last_session_message.assert_called_once_with("session-123")

        # Verify events: ToolCall, ToolResult, TextMessage
        assert len(events) == 3

        # First event should be ToolCall
        assert isinstance(events[0], ToolCall)
        assert events[0].tool_name == "edit_document"
        assert events[0].tool_call_id == "edit_document"
        assert events[0].tool_args["edits"][0]["find"] == "old"

        # Second event should be ToolResult with success
        assert isinstance(events[1], ToolResult)
        assert events[1].tool_call_id == "edit_document"
        assert "success" in events[1].result_content
        assert "Edit successful" in events[1].result_content
        assert events[1].is_error is False

        # Third event should be final TextMessage
        assert isinstance(events[2], TextMessage)
        assert events[2].text_content == "The document has been updated."

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    @patch("devboard.agents.engines.claude_code.agent.ClaudeCodeSessionService")
    async def test_tool_denial_with_feedback(
        self, mock_session_service_class, mock_client_class, agent_with_virtual_tool
    ):
        """Test processing denied tool call with feedback."""
        agent_with_virtual_tool.session_id = "session-123"

        # Create mock session message with virtual tool call
        tool_call_json = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_document",
                "arguments": {"edits": [{"find": "old", "replace": "new"}]},
            }
        )

        # Mock session service to return a message with tool call
        mock_session_service = mock_session_service_class.return_value
        mock_session_message = create_mock_session_message_with_tool_call(tool_call_json)
        mock_session_service.get_last_session_message.return_value = mock_session_message

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

        # Verify session service was called
        mock_session_service.get_last_session_message.assert_called_once_with("session-123")

        # Verify events: ToolCall, ToolResult (with denial), TextMessage
        assert len(events) == 3

        # First event should be ToolCall
        assert isinstance(events[0], ToolCall)
        assert events[0].tool_name == "edit_document"
        assert events[0].tool_call_id == "edit_document"

        # Second event should be ToolResult with denial
        assert isinstance(events[1], ToolResult)
        assert events[1].tool_call_id == "edit_document"
        assert "denied" in events[1].result_content
        assert "The edit is not appropriate" in events[1].result_content
        assert events[1].is_error is True

        # Third event should be final TextMessage
        assert isinstance(events[2], TextMessage)
        assert "different approach" in events[2].text_content

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

        async def mock_stream(user_query, **kwargs):
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

        async def mock_stream(user_query, **kwargs):
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

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_generator_cleanup_on_validation_error(self, mock_client_class, agent_with_virtual_tool):
        """Test that stream generator is properly closed when validation error occurs.

        This test ensures that when InvalidVirtualToolCallError is raised, the generator
        from client.stream() is explicitly closed via aclose() to prevent async context
        manager cleanup errors (RuntimeError: exit cancel scope in different task).
        """
        # First call: invalid tool call to trigger validation error
        invalid_tool_call = json.dumps(
            {"type": "tool_call", "tool_name": "unknown_tool", "arguments": {"param": "value"}}
        )
        # Second call: valid tool call
        valid_tool_call = json.dumps(
            {
                "type": "tool_call",
                "tool_name": "edit_document",
                "arguments": {"edits": [{"find": "old", "replace": "new"}]},
            }
        )

        call_count = 0
        generators_created = []

        class MockAsyncGenerator:
            """Mock async generator that tracks aclose() calls."""

            def __init__(self, messages):
                self.messages = messages
                self.index = 0
                self.closed = False
                generators_created.append(self)

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.messages):
                    raise StopAsyncIteration
                message = self.messages[self.index]
                self.index += 1
                return message

            async def aclose(self):
                self.closed = True

        def mock_stream(user_query, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockAsyncGenerator(create_mock_text_stream(invalid_tool_call))
            return MockAsyncGenerator(create_mock_text_stream(valid_tool_call))

        mock_client = AsyncMock()
        mock_client.stream = mock_stream
        mock_client_class.return_value = mock_client

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Verify aclose() was called on the first generator when validation error occurred
        assert len(generators_created) == 2, "Should have created 2 generators (one for each attempt)"
        assert generators_created[0].closed, "First generator aclose() was not called on validation error"
        # Verify retry succeeded
        assert call_count == 2
        assert len(events) == 1
        assert isinstance(events[0], ToolCallRequest)
        assert events[0].tool_name == "edit_document"


class TestStreamEventsSubagentFiltering:
    """Tests for filtering subagent messages from the conversation stream."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_filters_subagent_assistant_message(self, mock_client_class, agent_with_virtual_tool):
        """Test that AssistantMessage with parent_tool_use_id is filtered out."""
        subagent_msg = AssistantMessage(
            content=[TextBlock(text="Subagent message")],
            model="claude-sonnet-4",
            parent_tool_use_id="tool-parent-123",
        )
        final_messages = create_mock_text_stream("Parent response")
        setup_mock_client(mock_client_class, [subagent_msg] + final_messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test"):
            events.append(event)

        text_events = [e for e in events if isinstance(e, TextMessage)]
        assert len(text_events) == 1
        assert text_events[0].text_content == "Parent response"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_filters_subagent_user_message(self, mock_client_class, agent_with_virtual_tool):
        """Test that UserMessage with parent_tool_use_id is filtered out."""
        subagent_tool_result = ToolResultBlock(tool_use_id="tool-sub-1", content="Subagent result", is_error=False)
        subagent_user_msg = UserMessage(
            content=[subagent_tool_result],
            parent_tool_use_id="tool-parent-456",
        )
        final_messages = create_mock_text_stream("Parent response")
        setup_mock_client(mock_client_class, [subagent_user_msg] + final_messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test"):
            events.append(event)

        # No ToolResult from subagent, only parent text
        tool_result_events = [e for e in events if isinstance(e, ToolResult)]
        assert len(tool_result_events) == 0
        text_events = [e for e in events if isinstance(e, TextMessage)]
        assert len(text_events) == 1
        assert text_events[0].text_content == "Parent response"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_mixed_parent_and_subagent_messages(self, mock_client_class, agent_with_both_tools):
        """Test that only parent messages are converted to events in a mixed stream."""
        # Parent tool call
        tool_use = create_mock_tool_use_block("search_code", "tool-1", {"query": "test"})
        parent_assistant = AssistantMessage(content=[tool_use], model="claude-sonnet-4", parent_tool_use_id=None)

        # Subagent messages (should be filtered)
        subagent_assistant = AssistantMessage(
            content=[TextBlock(text="Subagent working...")],
            model="claude-sonnet-4",
            parent_tool_use_id="tool-parent-789",
        )
        subagent_user = UserMessage(
            content=[ToolResultBlock(tool_use_id="sub-tool-1", content="sub result", is_error=False)],
            parent_tool_use_id="tool-parent-789",
        )

        # Parent tool result
        parent_user = UserMessage(
            content=[ToolResultBlock(tool_use_id="tool-1", content="Found results", is_error=False)]
        )

        final_messages = create_mock_text_stream("Done")
        setup_mock_client(
            mock_client_class,
            [parent_assistant, subagent_assistant, subagent_user, parent_user] + final_messages,
        )

        events = []
        async for event in agent_with_both_tools.stream_events("Test"):
            events.append(event)

        # Should have: parent ToolCall, parent ToolResult, final TextMessage
        assert len(events) == 3
        assert isinstance(events[0], ToolCall)
        assert events[0].tool_call_id == "tool-1"
        assert isinstance(events[1], ToolResult)
        assert events[1].tool_call_id == "tool-1"
        assert isinstance(events[2], TextMessage)
        assert events[2].text_content == "Done"


class TestStreamEventsEdgeCases:
    """Tests for edge cases and error conditions."""

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


class TestStreamEventsApi500Retry:
    """Tests for stream_events() retry logic on API 500 errors."""

    def create_api_500_error_result_message(self, session_id: str = "test-session-123") -> ResultMessage:
        """Helper to create a ResultMessage with API 500 error."""
        return ResultMessage(
            subtype="error",
            duration_ms=1000,
            duration_api_ms=800,
            is_error=True,
            num_turns=1,
            session_id=session_id,
            total_cost_usd=0.001,
            result='API Error: 500 {"type":"error","error":{"type":"api_error","message":"Internal server error"},"request_id":"req_011CXoNGDoLWwez3NpZwQL8s"}',
        )

    def create_api_500_error_stream(self, session_id: str = "test-session-123") -> list:
        """Helper to create a message stream that ends with API 500 error."""
        error_text = 'API Error: 500 {"type":"error","error":{"type":"api_error","message":"Internal server error"}}'
        return [
            SystemMessage(subtype="session_start", data={"session_id": session_id}),
            create_mock_assistant_message_with_text(error_text),
            self.create_api_500_error_result_message(session_id),
        ]

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_api_500_error_triggers_retry_and_succeeds(self, mock_client_class, agent_with_virtual_tool):
        """Test that API 500 error triggers retry with 'continue' message and succeeds."""
        call_count = 0
        call_messages = []

        async def mock_stream(user_query, **kwargs):
            nonlocal call_count
            call_count += 1
            call_messages.append(user_query)
            if call_count == 1:
                # First call: return API 500 error
                for message in self.create_api_500_error_stream():
                    yield message
            else:
                # Second call: return success
                for message in create_mock_text_stream("Successfully recovered!"):
                    yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have called stream twice (initial + 1 retry)
        assert call_count == 2
        # Second call should have "continue" as the message
        assert call_messages[1] == "continue"

        # Should have SystemEvent for retry and final TextMessage
        from devboard.agents.events import SystemEvent, SystemEventType

        assert len(events) == 3  # Error text, SystemEvent, and success message
        # First event is the error text message streamed before ResultMessage
        assert isinstance(events[0], TextMessage)
        assert "API Error: 500" in events[0].text_content
        # Second event is the retry notification
        assert isinstance(events[1], SystemEvent)
        assert events[1].type == SystemEventType.API_ERROR_RETRY
        assert events[1].data["attempt"] == 1
        assert events[1].data["max_attempts"] == 3
        # Third event is the successful response
        assert isinstance(events[2], TextMessage)
        assert events[2].text_content == "Successfully recovered!"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_api_500_error_max_retries_exceeded_continues_normally(
        self, mock_client_class, agent_with_virtual_tool
    ):
        """Test that exceeding max retries for API 500 error continues without raising."""
        from devboard.agents.events import SystemEvent, SystemEventType

        call_count = 0

        async def mock_stream(user_query, **kwargs):
            nonlocal call_count
            call_count += 1
            # Always return API 500 error
            for message in self.create_api_500_error_stream():
                yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have called stream 4 times (initial + 3 retries)
        assert call_count == 4

        # Should have 4 error text messages + 3 retry SystemEvents (no retry on 4th attempt)
        text_events = [e for e in events if isinstance(e, TextMessage)]
        system_events = [e for e in events if isinstance(e, SystemEvent)]

        assert len(text_events) == 4  # One error message per attempt
        assert len(system_events) == 3  # Three retry notifications
        for i, event in enumerate(system_events):
            assert event.type == SystemEventType.API_ERROR_RETRY
            assert event.data["attempt"] == i + 1

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_non_500_api_error_not_retried(self, mock_client_class, agent_with_virtual_tool):
        """Test that non-500 API errors (e.g., 429) are not retried."""
        call_count = 0

        def create_api_429_error_stream():
            """Create a stream with 429 rate limit error."""
            error_text = 'API Error: 429 {"type":"error","error":{"type":"rate_limit_error","message":"Rate limited"}}'
            return [
                SystemMessage(subtype="session_start", data={"session_id": "test-session"}),
                create_mock_assistant_message_with_text(error_text),
                ResultMessage(
                    subtype="error",
                    duration_ms=1000,
                    duration_api_ms=800,
                    is_error=True,
                    num_turns=1,
                    session_id="test-session",
                    total_cost_usd=0.001,
                    result=error_text,
                ),
            ]

        async def mock_stream(user_query, **kwargs):
            nonlocal call_count
            call_count += 1
            for message in create_api_429_error_stream():
                yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have called stream only once (no retry for 429)
        assert call_count == 1
        # Should only have the error text message (ResultMessage is skipped)
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert "API Error: 429" in events[0].text_content

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_api_500_retry_preserves_session_id(self, mock_client_class, agent_with_virtual_tool):
        """Test that session_id is preserved across API 500 retries."""
        session_id = "preserved-session-456"
        call_count = 0

        async def mock_stream(user_query, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: return API 500 error with session_id
                for message in self.create_api_500_error_stream(session_id):
                    yield message
            else:
                # Second call: return success
                for message in create_mock_text_stream("Success!", session_id):
                    yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        # Start without session_id
        assert agent_with_virtual_tool.session_id is None

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Session ID should be set from the first stream
        assert agent_with_virtual_tool.session_id == session_id
        # Should have succeeded after retry
        assert call_count == 2


class TestShouldRetryErrorResult:
    """Tests for _should_retry_error_result() helper function."""

    def test_returns_true_for_api_500_error(self):
        """Test that API 500 errors are retryable."""
        result = 'API Error: 500 {"type":"error","error":{"type":"api_error","message":"Internal server error"}}'
        assert _should_retry_error_result(result) is True

    def test_returns_true_for_api_400_duplicate_tool_use_ids(self):
        """Test that API 400 with duplicate tool_use IDs is retryable."""
        result = 'API Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"messages.75.content.1: tool_use ids must be unique"}}'
        assert _should_retry_error_result(result) is True

    def test_returns_true_for_api_400_tool_use_concurrency(self):
        """Test that API 400 with tool use concurrency issues is retryable."""
        result = 'API Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"tool use concurrency issues detected"}}'
        assert _should_retry_error_result(result) is True

    def test_returns_false_for_non_retryable_api_400_error(self):
        """Test that other API 400 errors are not retryable."""
        result = 'API Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"invalid parameter value"}}'
        assert _should_retry_error_result(result) is False

    def test_returns_false_for_api_429_error(self):
        """Test that API 429 rate limit errors are not retryable."""
        result = 'API Error: 429 {"type":"error","error":{"type":"rate_limit_error","message":"Rate limited"}}'
        assert _should_retry_error_result(result) is False

    def test_returns_false_for_api_401_error(self):
        """Test that API 401 auth errors are not retryable."""
        result = 'API Error: 401 {"type":"error","error":{"type":"authentication_error","message":"Invalid API key"}}'
        assert _should_retry_error_result(result) is False

    def test_returns_false_for_none(self):
        """Test that None result is not retryable."""
        assert _should_retry_error_result(None) is False

    def test_returns_false_for_empty_string(self):
        """Test that empty string is not retryable."""
        assert _should_retry_error_result("") is False

    def test_returns_false_for_regular_text(self):
        """Test that regular text is not retryable."""
        assert _should_retry_error_result("Hello, how can I help you?") is False


class TestStreamEventsApi400Retry:
    """Tests for stream_events() retry logic on API 400 errors with duplicate tool_use IDs."""

    def create_api_400_error_result_message(
        self, error_message: str = "tool_use ids must be unique", session_id: str = "test-session-123"
    ) -> ResultMessage:
        """Helper to create a ResultMessage with API 400 error."""
        return ResultMessage(
            subtype="error",
            duration_ms=1000,
            duration_api_ms=800,
            is_error=False,  # Note: is_error may be False for API 400 errors from Claude CLI
            num_turns=1,
            session_id=session_id,
            total_cost_usd=0.001,
            result=f'API Error: 400 {{"type":"error","error":{{"type":"invalid_request_error","message":"messages.75.content.1: {error_message}"}},"request_id":"req_011CXoNGDoLWwez3NpZwQL8s"}}',
        )

    def create_api_400_error_stream(
        self, error_message: str = "tool_use ids must be unique", session_id: str = "test-session-123"
    ) -> list:
        """Helper to create a message stream that ends with API 400 error."""
        error_text = f'API Error: 400 {{"type":"error","error":{{"type":"invalid_request_error","message":"messages.75.content.1: {error_message}"}}}}'
        return [
            SystemMessage(subtype="session_start", data={"session_id": session_id}),
            create_mock_assistant_message_with_text(error_text),
            self.create_api_400_error_result_message(error_message, session_id),
        ]

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_api_400_duplicate_tool_use_ids_triggers_retry(self, mock_client_class, agent_with_virtual_tool):
        """Test that API 400 with 'tool_use ids must be unique' triggers retry."""
        call_count = 0
        call_messages = []

        async def mock_stream(user_query, **kwargs):
            nonlocal call_count
            call_count += 1
            call_messages.append(user_query)
            if call_count == 1:
                # First call: return API 400 error with duplicate tool_use IDs
                for message in self.create_api_400_error_stream("tool_use ids must be unique"):
                    yield message
            else:
                # Second call: return success
                for message in create_mock_text_stream("Successfully recovered!"):
                    yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have called stream twice (initial + 1 retry)
        assert call_count == 2
        # Second call should have "continue" as the message
        assert call_messages[1] == "continue"

        # Should have SystemEvent for retry and final TextMessage
        from devboard.agents.events import SystemEvent, SystemEventType

        assert len(events) == 3  # Error text, SystemEvent, and success message
        # First event is the error text message streamed before ResultMessage
        assert isinstance(events[0], TextMessage)
        assert "API Error: 400" in events[0].text_content
        assert "tool_use ids must be unique" in events[0].text_content
        # Second event is the retry notification
        assert isinstance(events[1], SystemEvent)
        assert events[1].type == SystemEventType.API_ERROR_RETRY
        assert events[1].data["attempt"] == 1
        assert events[1].data["max_attempts"] == 3
        # Third event is the successful response
        assert isinstance(events[2], TextMessage)
        assert events[2].text_content == "Successfully recovered!"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_api_400_retry_works_even_without_is_error_flag(self, mock_client_class, agent_with_virtual_tool):
        """Test that API 400 retry works even when is_error=False in ResultMessage.

        This is the key fix - the Claude CLI may not set is_error=True for API 400 errors,
        so we check the result content regardless of the is_error flag.
        """
        call_count = 0

        async def mock_stream(user_query, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Create error with is_error=False to simulate CLI behavior
                error_text = 'API Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"messages.75.content.1: tool_use ids must be unique"}}'
                yield SystemMessage(subtype="session_start", data={"session_id": "test-session"})
                yield create_mock_assistant_message_with_text(error_text)
                yield ResultMessage(
                    subtype="error",
                    duration_ms=1000,
                    duration_api_ms=800,
                    is_error=False,  # Note: is_error is False
                    num_turns=1,
                    session_id="test-session",
                    total_cost_usd=0.001,
                    result=error_text,
                )
            else:
                for message in create_mock_text_stream("Success!"):
                    yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have retried even though is_error was False
        assert call_count == 2

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_api_400_max_retries_exceeded_continues_normally(self, mock_client_class, agent_with_virtual_tool):
        """Test that exceeding max retries for API 400 error continues without raising."""
        from devboard.agents.events import SystemEvent, SystemEventType

        call_count = 0

        async def mock_stream(user_query, **kwargs):
            nonlocal call_count
            call_count += 1
            # Always return API 400 error
            for message in self.create_api_400_error_stream("tool_use ids must be unique"):
                yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have called stream 4 times (initial + 3 retries)
        assert call_count == 4

        # Should have 4 error text messages + 3 retry SystemEvents (no retry on 4th attempt)
        text_events = [e for e in events if isinstance(e, TextMessage)]
        system_events = [e for e in events if isinstance(e, SystemEvent)]

        assert len(text_events) == 4  # One error message per attempt
        assert len(system_events) == 3  # Three retry notifications
        for i, event in enumerate(system_events):
            assert event.type == SystemEventType.API_ERROR_RETRY
            assert event.data["attempt"] == i + 1

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_api_400_non_retryable_error_not_retried(self, mock_client_class, agent_with_virtual_tool):
        """Test that non-retryable API 400 errors are not retried."""
        call_count = 0

        def create_non_retryable_400_error_stream():
            """Create a stream with non-retryable 400 error."""
            error_text = 'API Error: 400 {"type":"error","error":{"type":"invalid_request_error","message":"invalid parameter value"}}'
            return [
                SystemMessage(subtype="session_start", data={"session_id": "test-session"}),
                create_mock_assistant_message_with_text(error_text),
                ResultMessage(
                    subtype="error",
                    duration_ms=1000,
                    duration_api_ms=800,
                    is_error=True,
                    num_turns=1,
                    session_id="test-session",
                    total_cost_usd=0.001,
                    result=error_text,
                ),
            ]

        async def mock_stream(user_query, **kwargs):
            nonlocal call_count
            call_count += 1
            for message in create_non_retryable_400_error_stream():
                yield message

        setup_mock_client_with_callback(mock_client_class, mock_stream)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have called stream only once (no retry for non-retryable 400)
        assert call_count == 1
        # Should only have the error text message
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert "API Error: 400" in events[0].text_content
        assert "invalid parameter value" in events[0].text_content


class TestStreamEventsThinkingBlock:
    """Tests for stream_events() with ThinkingBlock content."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_thinking_block_yields_thinking_event(self, mock_client_class, agent_with_virtual_tool):
        """Test that a ThinkingBlock yields a ThinkingEvent."""
        session_id = "test-session-thinking"
        thinking_message = AssistantMessage(
            content=[ThinkingBlock(thinking="Let me think about this...", signature="sig")],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )
        messages = [
            SystemMessage(subtype="session_start", data={"session_id": session_id}),
            thinking_message,
            create_mock_result_message("", session_id=session_id),
        ]
        setup_mock_client(mock_client_class, messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ThinkingEvent)

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.agent.ClaudeClient")
    async def test_thinking_block_followed_by_text(self, mock_client_class, agent_with_virtual_tool):
        """Test that ThinkingBlock + TextBlock yields ThinkingEvent then TextMessage."""
        session_id = "test-session-thinking-text"
        mixed_message = AssistantMessage(
            content=[
                ThinkingBlock(thinking="Reasoning here...", signature="sig"),
                TextBlock(text="Here is my answer."),
            ],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )
        messages = [
            SystemMessage(subtype="session_start", data={"session_id": session_id}),
            mixed_message,
            create_mock_result_message("Here is my answer.", session_id=session_id),
        ]
        setup_mock_client(mock_client_class, messages)

        events = []
        async for event in agent_with_virtual_tool.stream_events("Test prompt"):
            events.append(event)

        assert len(events) == 2
        assert isinstance(events[0], ThinkingEvent)
        assert isinstance(events[1], TextMessage)
        assert events[1].text_content == "Here is my answer."
        assert events[1].role == MessageRole.AGENT
