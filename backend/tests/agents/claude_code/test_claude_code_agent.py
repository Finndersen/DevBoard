"""Tests for ClaudeClient."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from devboard.agents.engines.claude_code.client import ClaudeClient, ClaudeCodeResult


@pytest.fixture
def mock_sdk_client():
    """Create a mock ClaudeSDKClient."""
    with patch("devboard.agents.engines.claude_code.client.ClaudeSDKClient") as mock_class:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_class.return_value = mock_instance
        yield mock_instance


class TestClaudeClient:
    """Test suite for ClaudeClient."""

    def test_init_without_session(self):
        """Test agent initialization without session ID."""
        agent = ClaudeClient()
        assert agent.session_id is None
        assert agent.options.resume is None

    def test_init_with_session(self):
        """Test agent initialization with session ID."""
        session_id = "test-session-123"
        agent = ClaudeClient(session_id=session_id)
        assert agent.session_id == session_id
        assert agent.options.resume == session_id

    def test_init_with_tools(self):
        """Test agent initialization with custom tools."""

        async def custom_tool(name: str, count: int = 1) -> str:
            """A custom test tool.

            Args:
                name: The name to greet
                count: Number of times to greet
            """
            return f"Hello {name}! " * count

        agent = ClaudeClient(tools=[custom_tool])
        assert agent.options.mcp_servers is not None
        assert "devboard_tools" in agent.options.mcp_servers
        assert len(agent.options.allowed_tools) == 1
        assert agent.options.allowed_tools[0] == "mcp__devboard_tools__custom_tool"

    @pytest.mark.asyncio
    async def test_run_basic_query(self, mock_sdk_client):
        """Test basic query execution with run()."""
        # Setup mock response
        text_block = TextBlock(text="Hello, this is Claude!")
        assistant_msg = AssistantMessage(
            content=[text_block],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )
        result_msg = ResultMessage(
            subtype="complete",
            duration_ms=1000,
            duration_api_ms=800,
            is_error=False,
            num_turns=1,
            session_id="session-123",
            total_cost_usd=0.001,
            result="Hello, this is Claude!",
        )

        async def mock_receive_response():
            """Mock async iterator for receive_response."""
            yield assistant_msg
            yield result_msg

        mock_sdk_client.receive_response = mock_receive_response

        # Execute query
        agent = ClaudeClient()
        result = await agent.run("Hello Claude")

        # Verify result
        assert isinstance(result, ClaudeCodeResult)
        assert result.text_content == "Hello, this is Claude!"
        assert result.session_id == "session-123"
        assert result.result_message.total_cost_usd == 0.001
        assert result.result_message.is_error is False

        # Verify client was called correctly
        mock_sdk_client.query.assert_called_once_with("Hello Claude")

    @pytest.mark.asyncio
    async def test_run_with_session_id(self, mock_sdk_client):
        """Test query execution with existing session ID."""
        text_block = TextBlock(text="Resumed conversation")
        assistant_msg = AssistantMessage(
            content=[text_block],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )
        result_msg = ResultMessage(
            subtype="complete",
            duration_ms=500,
            duration_api_ms=400,
            is_error=False,
            num_turns=2,
            session_id="existing-session",
            result="Resumed conversation",
        )

        async def mock_receive_response():
            yield assistant_msg
            yield result_msg

        mock_sdk_client.receive_response = mock_receive_response

        # Execute with session ID
        agent = ClaudeClient(session_id="existing-session")
        result = await agent.run("Continue our chat")

        assert result.session_id == "existing-session"
        mock_sdk_client.query.assert_called_once_with("Continue our chat")

    @pytest.mark.asyncio
    async def test_run_multiple_text_blocks(self, mock_sdk_client):
        """Test handling of multiple text blocks in response."""
        text1 = TextBlock(text="First part")
        text2 = TextBlock(text="Second part")
        assistant_msg = AssistantMessage(
            content=[text1, text2],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )
        result_msg = ResultMessage(
            subtype="complete",
            duration_ms=1000,
            duration_api_ms=800,
            is_error=False,
            num_turns=1,
            session_id="session-456",
            result="First part\nSecond part",
        )

        async def mock_receive_response():
            yield assistant_msg
            yield result_msg

        mock_sdk_client.receive_response = mock_receive_response

        agent = ClaudeClient()
        result = await agent.run("Test query")

        # Verify text blocks are joined
        assert result.text_content == "First part\nSecond part"

    @pytest.mark.asyncio
    async def test_run_no_result_message_raises_error(self, mock_sdk_client):
        """Test that missing ResultMessage raises an error."""
        text_block = TextBlock(text="Some text")
        assistant_msg = AssistantMessage(
            content=[text_block],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )

        async def mock_receive_response():
            yield assistant_msg
            # No ResultMessage yielded

        mock_sdk_client.receive_response = mock_receive_response

        agent = ClaudeClient()
        with pytest.raises(RuntimeError, match="No ResultMessage received"):
            await agent.run("Test query")

    @pytest.mark.asyncio
    async def test_stream_basic(self, mock_sdk_client):
        """Test streaming messages."""
        text_block = TextBlock(text="Streaming response")
        assistant_msg = AssistantMessage(
            content=[text_block],
            model="claude-sonnet-4",
            parent_tool_use_id=None,
        )
        result_msg = ResultMessage(
            subtype="complete",
            duration_ms=1000,
            duration_api_ms=800,
            is_error=False,
            num_turns=1,
            session_id="stream-session",
        )

        async def mock_receive_response():
            yield assistant_msg
            yield result_msg

        mock_sdk_client.receive_response = mock_receive_response

        # Collect streamed messages
        agent = ClaudeClient()
        messages = []
        async for message in agent.stream("Stream test"):
            messages.append(message)

        # Verify messages
        assert len(messages) == 2
        assert isinstance(messages[0], AssistantMessage)
        assert isinstance(messages[1], ResultMessage)
        assert messages[1].session_id == "stream-session"

        mock_sdk_client.query.assert_called_once_with("Stream test")

    @pytest.mark.asyncio
    async def test_stream_with_session_id(self, mock_sdk_client):
        """Test streaming with existing session ID."""
        result_msg = ResultMessage(
            subtype="complete",
            duration_ms=500,
            duration_api_ms=400,
            is_error=False,
            num_turns=1,
            session_id="stream-session-2",
        )

        async def mock_receive_response():
            yield result_msg

        mock_sdk_client.receive_response = mock_receive_response

        agent = ClaudeClient(session_id="stream-session-2")
        messages = []
        async for message in agent.stream("Stream with session"):
            messages.append(message)

        assert len(messages) == 1
        mock_sdk_client.query.assert_called_once_with("Stream with session")

    @pytest.mark.asyncio
    async def test_tool_wrapper_with_string_return(self):
        """Test that tool wrapper correctly handles string returns."""

        def simple_tool(text: str) -> str:
            """A simple tool that returns a string.

            Args:
                text: Input text to process
            """
            return f"Processed: {text}"

        from pydantic.json_schema import GenerateJsonSchema
        from pydantic_ai._function_schema import function_schema

        # Create schema and wrapper
        schema = function_schema(
            function=simple_tool,
            schema_generator=GenerateJsonSchema,
            takes_ctx=False,
        )
        wrapper = ClaudeClient._create_tool_wrapper(simple_tool, schema)

        # Test the wrapper
        result = await wrapper({"text": "hello"})
        assert isinstance(result, dict)
        assert "content" in result
        assert result["content"] == [{"type": "text", "text": "Processed: hello"}]

    @pytest.mark.asyncio
    async def test_tool_wrapper_with_dict_return(self):
        """Test that tool wrapper correctly handles dict returns with content."""

        async def dict_tool(value: int) -> dict[str, Any]:
            """A tool that returns a dict.

            Args:
                value: Input value
            """
            return {"content": [{"type": "text", "text": f"Value: {value}"}]}

        from pydantic.json_schema import GenerateJsonSchema
        from pydantic_ai._function_schema import function_schema

        # Create schema and wrapper
        schema = function_schema(
            function=dict_tool,
            schema_generator=GenerateJsonSchema,
            takes_ctx=False,
        )
        wrapper = ClaudeClient._create_tool_wrapper(dict_tool, schema)

        # Test the wrapper
        result = await wrapper({"value": 42})
        assert result == {"content": [{"type": "text", "text": "Value: 42"}]}

    @pytest.mark.asyncio
    async def test_tool_wrapper_validates_arguments(self):
        """Test that tool wrapper validates arguments using schema."""

        def typed_tool(count: int, name: str) -> str:
            """A tool with typed parameters.

            Args:
                count: A number
                name: A string
            """
            return f"{name}: {count}"

        from pydantic.json_schema import GenerateJsonSchema
        from pydantic_ai._function_schema import function_schema
        from pydantic_core import ValidationError

        # Create schema and wrapper
        schema = function_schema(
            function=typed_tool,
            schema_generator=GenerateJsonSchema,
            takes_ctx=False,
        )
        wrapper = ClaudeClient._create_tool_wrapper(typed_tool, schema)

        # Test with valid arguments
        result = await wrapper({"count": 5, "name": "test"})
        assert result["content"][0]["text"] == "test: 5"

        # Test with invalid arguments (wrong type)
        with pytest.raises(ValidationError):
            await wrapper({"count": "not a number", "name": "test"})
