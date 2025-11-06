"""Comprehensive tests for InternalAgent.stream_events() method."""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from pydantic_ai import AgentRunResultEvent, FunctionToolCallEvent, FunctionToolResultEvent, Tool
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult
from pydantic_ai.tools import DeferredToolRequests

from devboard.agents.engines.internal.agent import InternalAgent
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


def create_mock_agent_run_result(output: str | DeferredToolRequests, new_messages: list[ModelMessage] | None = None):
    """Helper to create a mock AgentRunResult."""
    result = Mock(spec=AgentRunResult)
    result.output = output
    result.new_messages = Mock(return_value=new_messages or [])
    return result


def create_pydantic_tool_call_event(tool_name: str, tool_call_id: str, args: dict[str, Any]) -> FunctionToolCallEvent:
    """Helper to create a PydanticAI FunctionToolCallEvent."""
    tool_call_part = ToolCallPart(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        args=args,
    )
    return FunctionToolCallEvent(part=tool_call_part)


def create_pydantic_tool_result_event(
    tool_call_id: str, content: str, is_error: bool = False
) -> FunctionToolResultEvent:
    """Helper to create a PydanticAI FunctionToolResultEvent."""
    tool_return_part = ToolReturnPart(
        tool_name="test_tool",  # Required but not used in our conversion
        tool_call_id=tool_call_id,
        content=content,
    )
    return FunctionToolResultEvent(result=tool_return_part)


def create_pydantic_result_event(output: str | DeferredToolRequests) -> AgentRunResultEvent:
    """Helper to create a PydanticAI AgentRunResultEvent."""
    result = create_mock_agent_run_result(output)
    return AgentRunResultEvent(result=result)


def setup_mock_pydantic_agent(mock_agent_class, events_to_yield):
    """Helper to set up a mock PydanticAI Agent that yields specified events.

    Args:
        mock_agent_class: The patched Agent class
        events_to_yield: Single event or list of events to yield from run_stream_events

    Returns:
        The mock agent instance
    """
    mock_agent = Mock()

    # Ensure events_to_yield is a list
    if not isinstance(events_to_yield, list):
        events_to_yield = [events_to_yield]

    async def mock_stream(*args, **kwargs):
        for event in events_to_yield:
            yield event

    mock_agent.run_stream_events = mock_stream
    mock_agent_class.return_value = mock_agent
    return mock_agent


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
def mock_function_tool() -> Tool:
    """Create a mock function tool."""

    def search_code_fn(query: str, file_pattern: str = "*") -> str:
        return "Search results"

    return Tool(function=search_code_fn, name="search_code", requires_approval=False)


@pytest.fixture
def mock_approval_tool() -> Tool:
    """Create a mock tool that requires approval."""

    def edit_file_fn(path: str, content: str) -> str:
        return "File edited"

    return Tool(function=edit_file_fn, name="edit_file", requires_approval=True)


@pytest.fixture
def agent_with_function_tool(mock_model: LanguageModel, mock_function_tool: Tool) -> InternalAgent:
    """Create an agent with a function tool."""
    role = MockRole(tools=[mock_function_tool])
    return InternalAgent(role=role, model=mock_model)


@pytest.fixture
def agent_with_approval_tool(mock_model: LanguageModel, mock_approval_tool: Tool) -> InternalAgent:
    """Create an agent with an approval-required tool."""
    role = MockRole(tools=[mock_approval_tool])
    return InternalAgent(role=role, model=mock_model)


class TestStreamEventsTextResponse:
    """Tests for stream_events() with simple text responses."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_simple_text_response(self, mock_agent_class, agent_with_function_tool):
        """Test streaming a simple text response."""
        result_event = create_pydantic_result_event("Hello, this is a text response!")
        setup_mock_pydantic_agent(mock_agent_class, result_event)

        events = []
        async for event in agent_with_function_tool.stream_events("Test prompt"):
            events.append(event)

        # Should have one ConversationMessage
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == MessageRole.AGENT
        assert events[0].text_content == "Hello, this is a text response!"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_multiline_text_response(self, mock_agent_class, agent_with_function_tool):
        """Test streaming a multiline text response."""
        multiline_text = "Line 1\nLine 2\nLine 3"
        result_event = create_pydantic_result_event(multiline_text)
        setup_mock_pydantic_agent(mock_agent_class, result_event)

        events = []
        async for event in agent_with_function_tool.stream_events("Test prompt"):
            events.append(event)

        assert len(events) == 1
        assert events[0].text_content == multiline_text

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_conversation_history_updated(self, mock_agent_class, agent_with_function_tool):
        """Test that conversation history is updated after each run."""
        # Create a mock result with new messages
        new_msg = ModelRequest(parts=[UserPromptPart(content="User query")])
        result = create_mock_agent_run_result("Response", new_messages=[new_msg])
        result_event = AgentRunResultEvent(result=result)

        setup_mock_pydantic_agent(mock_agent_class, result_event)

        # Initially empty
        assert len(agent_with_function_tool.conversation_history) == 0

        events = []
        async for event in agent_with_function_tool.stream_events("Test prompt"):
            events.append(event)

        # History should be updated
        assert len(agent_with_function_tool.conversation_history) == 1
        assert agent_with_function_tool.conversation_history[0] == new_msg


class TestStreamEventsDeferredToolRequests:
    """Tests for stream_events() with deferred tool requests (require approval)."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_deferred_tool_request(self, mock_agent_class, agent_with_approval_tool):
        """Test streaming a deferred tool request."""
        # Create a deferred tool request using ToolCallPart
        tool_call = ToolCallPart(
            tool_call_id="call-123",
            tool_name="edit_file",
            args={"path": "/test.py", "content": "new content"},
        )
        deferred_requests = DeferredToolRequests(approvals=[tool_call])
        result_event = create_pydantic_result_event(deferred_requests)

        setup_mock_pydantic_agent(mock_agent_class, result_event)

        events = []
        async for event in agent_with_approval_tool.stream_events("Edit the file"):
            events.append(event)

        # Should have one ToolCallRequest
        assert len(events) == 1
        assert isinstance(events[0], ToolCallRequest)
        assert events[0].tool_call_id == "call-123"
        assert events[0].tool_name == "edit_file"
        assert events[0].tool_args["path"] == "/test.py"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_multiple_deferred_tool_requests(self, mock_agent_class, agent_with_approval_tool):
        """Test streaming multiple deferred tool requests."""
        tool_call_1 = ToolCallPart(
            tool_call_id="call-1", tool_name="edit_file", args={"path": "/file1.py", "content": "content1"}
        )
        tool_call_2 = ToolCallPart(
            tool_call_id="call-2", tool_name="edit_file", args={"path": "/file2.py", "content": "content2"}
        )
        deferred_requests = DeferredToolRequests(approvals=[tool_call_1, tool_call_2])
        result_event = create_pydantic_result_event(deferred_requests)

        setup_mock_pydantic_agent(mock_agent_class, result_event)

        events = []
        async for event in agent_with_approval_tool.stream_events("Edit files"):
            events.append(event)

        # Should have two ToolCallRequest events
        assert len(events) == 2
        assert all(isinstance(e, ToolCallRequest) for e in events)
        assert events[0].tool_call_id == "call-1"
        assert events[1].tool_call_id == "call-2"


class TestStreamEventsFunctionToolCalls:
    """Tests for stream_events() with function tool calls (automatic execution)."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_function_tool_call_and_result(self, mock_agent_class, agent_with_function_tool):
        """Test streaming function tool calls and results."""
        # Create tool call and result events
        tool_call_event = create_pydantic_tool_call_event(
            tool_name="search_code", tool_call_id="call-123", args={"query": "test", "file_pattern": "*.py"}
        )
        tool_result_event = create_pydantic_tool_result_event(tool_call_id="call-123", content="Found 5 matches")
        result_event = create_pydantic_result_event("Here are the search results...")

        setup_mock_pydantic_agent(mock_agent_class, [tool_call_event, tool_result_event, result_event])

        events = []
        async for event in agent_with_function_tool.stream_events("Search for test"):
            events.append(event)

        # Should have: ToolCall, ToolResult, and final message
        assert len(events) == 3
        assert isinstance(events[0], ToolCall)
        assert events[0].tool_name == "search_code"
        assert events[0].tool_call_id == "call-123"

        assert isinstance(events[1], ToolResult)
        assert events[1].tool_call_id == "call-123"
        assert events[1].result_content == "Found 5 matches"
        assert events[1].is_error is False

        assert isinstance(events[2], TextMessage)
        assert events[2].text_content == "Here are the search results..."

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_multiple_tool_calls(self, mock_agent_class, agent_with_function_tool):
        """Test streaming multiple tool calls in sequence."""
        call1 = create_pydantic_tool_call_event("search_code", "call-1", {"query": "foo"})
        result1 = create_pydantic_tool_result_event("call-1", "Results for foo")

        call2 = create_pydantic_tool_call_event("search_code", "call-2", {"query": "bar"})
        result2 = create_pydantic_tool_result_event("call-2", "Results for bar")

        final_result = create_pydantic_result_event("Analysis complete")

        setup_mock_pydantic_agent(mock_agent_class, [call1, result1, call2, result2, final_result])

        events = []
        async for event in agent_with_function_tool.stream_events("Search code"):
            events.append(event)

        # Should have 5 events total
        assert len(events) == 5
        assert isinstance(events[0], ToolCall)
        assert isinstance(events[1], ToolResult)
        assert isinstance(events[2], ToolCall)
        assert isinstance(events[3], ToolResult)
        assert isinstance(events[4], TextMessage)


class TestStreamEventsToolApprovals:
    """Tests for stream_events() processing tool approvals."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_tool_approval_processed(self, mock_agent_class, agent_with_approval_tool):
        """Test processing approved tool call."""
        result_event = create_pydantic_result_event("File has been edited successfully")

        setup_mock_pydantic_agent(mock_agent_class, result_event)

        # Create tool approvals
        approvals = ToolApprovals(approvals={"call-123": ToolApprovalDecision(approved=True, feedback=None)})

        events = []
        async for event in agent_with_approval_tool.stream_events(approvals):
            events.append(event)

        # Should process approvals and return response
        assert len(events) >= 1
        assert isinstance(events[-1], TextMessage)

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_tool_denial_processed(self, mock_agent_class, agent_with_approval_tool):
        """Test processing denied tool call."""
        result_event = create_pydantic_result_event("I understand. Let me try a different approach.")

        setup_mock_pydantic_agent(mock_agent_class, result_event)

        # Create tool approvals (denied)
        approvals = ToolApprovals(
            approvals={"call-123": ToolApprovalDecision(approved=False, feedback="This change is not appropriate")}
        )

        events = []
        async for event in agent_with_approval_tool.stream_events(approvals):
            events.append(event)

        assert len(events) >= 1
        # Should get a response acknowledging the denial
        assert any("different approach" in e.text_content for e in events if isinstance(e, TextMessage))


class TestStreamEventsEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_no_result_raises_error(self, mock_agent_class, agent_with_function_tool):
        """Test that missing result raises ValueError."""

        async def mock_stream(*args, **kwargs):
            # Empty stream - no events yielded
            return
            yield  # Make this an async generator

        mock_agent = Mock()
        mock_agent.run_stream_events = mock_stream
        mock_agent_class.return_value = mock_agent

        with pytest.raises(ValueError, match="Agent execution did not produce a result"):
            events = []
            async for event in agent_with_function_tool.stream_events("Test prompt"):
                events.append(event)

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_unexpected_output_type_raises_error(self, mock_agent_class, agent_with_function_tool):
        """Test that unexpected output type raises ValueError."""
        # Create a result with an unexpected output type
        result = Mock(spec=AgentRunResult)
        result.output = {"unexpected": "dict"}  # Not str or DeferredToolRequests
        result.new_messages = Mock(return_value=[])
        result_event = AgentRunResultEvent(result=result)

        setup_mock_pydantic_agent(mock_agent_class, result_event)

        with pytest.raises(ValueError, match="Unexpected agent result output"):
            events = []
            async for event in agent_with_function_tool.stream_events("Test prompt"):
                events.append(event)

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_system_context_added_to_history(self, mock_agent_class, agent_with_function_tool):
        """Test that system prompt and context are added to message history."""
        result_event = create_pydantic_result_event("Response")

        # Track what was passed to run_stream_events
        call_args = None

        async def mock_stream(*args, **kwargs):
            nonlocal call_args
            call_args = kwargs
            yield result_event

        mock_agent = Mock()
        mock_agent.run_stream_events = mock_stream
        mock_agent_class.return_value = mock_agent

        events = []
        async for event in agent_with_function_tool.stream_events("Test prompt"):
            events.append(event)

        # Verify message_history was passed and contains system context
        assert call_args is not None
        assert "message_history" in call_args
        message_history = call_args["message_history"]

        # Should have system prompt + dummy response + any conversation history
        assert len(message_history) >= 2
        # First message should be the system/context request
        assert isinstance(message_history[0], ModelRequest)
        # Second message should be the dummy response
        assert isinstance(message_history[1], ModelResponse)

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.internal.agent.Agent")
    async def test_empty_output_string(self, mock_agent_class, agent_with_function_tool):
        """Test handling empty output string."""
        result_event = create_pydantic_result_event("")

        setup_mock_pydantic_agent(mock_agent_class, result_event)

        events = []
        async for event in agent_with_function_tool.stream_events("Test prompt"):
            events.append(event)

        # Should handle empty string gracefully
        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].text_content == ""
