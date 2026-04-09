"""Tests for ClaudeClient."""

import asyncio
import contextlib
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
)
from claude_agent_sdk import (
    tool as sdk_tool,
)
from mcp.types import CallToolRequest, CallToolRequestParams
from pydantic_ai import Tool
from pydantic_core import ValidationError

from devboard.agents.engines.claude_code.client import ClaudeClient, ClaudeCodeResult
from devboard.agents.engines.claude_code.utils import BUILTIN_TOOLS_MCP_NAME


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

    def test_init_sandbox_enabled_by_default(self):
        """Test that sandboxing is enabled by default with allowUnsandboxedCommands=False."""
        agent = ClaudeClient()
        assert agent.options.sandbox == {"enabled": True, "allowUnsandboxedCommands": False}

    def test_init_sandbox_disabled(self):
        """Test that passing sandbox_enabled=False sets sandbox to None."""
        agent = ClaudeClient(sandbox_enabled=False)
        assert agent.options.sandbox is None

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

        # Create PydanticAI Tool instance
        tool = Tool(custom_tool, name="custom_tool")

        agent = ClaudeClient(tools=[tool], load_settings=False)
        assert agent.options.mcp_servers is not None
        assert BUILTIN_TOOLS_MCP_NAME in agent.options.mcp_servers
        assert len(agent.options.allowed_tools) == 1
        assert agent.options.allowed_tools[0] == f"mcp__{BUILTIN_TOOLS_MCP_NAME}__custom_tool"
        assert agent.options.disallowed_tools is not None

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

        # Create PydanticAI Tool instance
        pydantic_tool = Tool(simple_tool, name="simple_tool")

        # Create wrapper using a ClaudeClient instance
        client = ClaudeClient(load_settings=False)
        wrapper = client._create_tool_execution_wrapper(pydantic_tool, validate_args=True)

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

        # Create PydanticAI Tool instance
        pydantic_tool = Tool(dict_tool, name="dict_tool")

        # Create wrapper using a ClaudeClient instance
        client = ClaudeClient(load_settings=False)
        wrapper = client._create_tool_execution_wrapper(pydantic_tool, validate_args=True)

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

        # Create PydanticAI Tool instance
        pydantic_tool = Tool(typed_tool, name="typed_tool")

        # Create wrapper using a ClaudeClient instance
        client = ClaudeClient(load_settings=False)
        wrapper = client._create_tool_execution_wrapper(pydantic_tool, validate_args=True)

        # Test with valid arguments
        result = await wrapper({"count": 5, "name": "test"})
        assert result["content"][0]["text"] == "test: 5"

        # Test with invalid arguments (wrong type) - should raise ValidationError
        with pytest.raises(ValidationError):
            await wrapper({"count": "not a number", "name": "test"})


class TestAdditionalWriteDirs:
    """Tests for additional_write_dirs functionality in ClaudeClient."""

    def test_additional_write_dirs_added_to_allowed_tools(self):
        """Test that additional_write_dirs results in Edit(<dir>/**) entries in allowed_tools."""
        client = ClaudeClient(
            allowed_builtin_tools=["Read"],
            additional_write_dirs=["/some/path"],
            load_settings=False,
        )
        assert "Edit(/some/path/**)" in client.options.allowed_tools

    def test_multiple_additional_write_dirs(self):
        """Test that multiple additional_write_dirs all get Edit entries."""
        client = ClaudeClient(
            allowed_builtin_tools=["Read"],
            additional_write_dirs=["/path/one", "/path/two"],
            load_settings=False,
        )
        assert "Edit(/path/one/**)" in client.options.allowed_tools
        assert "Edit(/path/two/**)" in client.options.allowed_tools

    def test_additional_write_dirs_none_adds_no_extra_entries(self):
        """Test that additional_write_dirs=None adds no extra Edit entries."""
        client_with_none = ClaudeClient(
            allowed_builtin_tools=["Read"],
            additional_write_dirs=None,
            load_settings=False,
        )
        client_without = ClaudeClient(
            allowed_builtin_tools=["Read"],
            load_settings=False,
        )
        assert client_with_none.options.allowed_tools == client_without.options.allowed_tools

    def test_additional_write_dirs_combined_with_allowed_builtin_tools(self):
        """Test that Edit entries are added alongside allowed builtin tools."""
        client = ClaudeClient(
            allowed_builtin_tools=["Read", "Bash"],
            additional_write_dirs=["/repo/main"],
            load_settings=False,
        )
        assert "Read" in client.options.allowed_tools
        assert "Bash" in client.options.allowed_tools
        assert "Edit(/repo/main/**)" in client.options.allowed_tools


class TestMcpToolErrorHandling:
    """Tests for MCP tool error handling behavior."""

    @pytest.mark.asyncio
    async def test_mcp_tool_exception_sets_is_error_flag(self):
        """Test that when a tool raises an exception, MCP sets is_error=True on the result.

        This verifies the MCP server properly flags tool errors so they can be
        distinguished from successful results by the claude-agent-sdk.
        """

        # Create a tool that raises an exception
        @sdk_tool(name="failing_tool", description="A tool that always fails", input_schema={})
        async def failing_tool(_args: dict) -> dict:
            raise ValueError("Intentional test error")

        # Create MCP server with the failing tool
        server_config = create_sdk_mcp_server(
            name="test_server",
            version="1.0.0",
            tools=[failing_tool],
        )
        server = server_config["instance"]

        # Get the call_tool handler
        handler = server.request_handlers.get(CallToolRequest)
        assert handler is not None

        # Call the tool
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(name="failing_tool", arguments={}),
        )
        result = await handler(request)

        # Verify the result has isError=True (MCP uses camelCase)
        assert hasattr(result.root, "isError"), "Result should have isError attribute"
        assert result.root.isError is True, "isError should be True when tool raises exception"
        assert len(result.root.content) == 1
        assert "Intentional test error" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_mcp_tool_success_does_not_set_is_error_flag(self):
        """Test that successful tool execution does not set is_error flag."""

        @sdk_tool(name="success_tool", description="A tool that succeeds", input_schema={})
        async def success_tool(_args: dict) -> dict:
            return {"content": [{"type": "text", "text": "Success!"}]}

        server_config = create_sdk_mcp_server(
            name="test_server",
            version="1.0.0",
            tools=[success_tool],
        )
        server = server_config["instance"]

        handler = server.request_handlers.get(CallToolRequest)
        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(name="success_tool", arguments={}),
        )
        result = await handler(request)

        # Verify isError is False for successful execution (MCP uses camelCase)
        assert hasattr(result.root, "isError"), "Result should have isError attribute"
        assert result.root.isError is False, "isError should be False for successful tool"


class TestStreamGracefulShutdown:
    """Tests for stream() finally block graceful shutdown behavior.

    The stream() method uses a queue-based approach with a background _consume_sdk task.
    When the consumer exits early, the finally block should give the task a grace period
    to complete (for subprocess flush) before resorting to cancellation.
    """

    @pytest.mark.asyncio
    async def test_natural_stream_exhaustion_no_cancel(self, mock_sdk_client):
        """Verify that when the stream exhausts naturally, no cancellation occurs."""

        async def mock_receive_response():
            yield AssistantMessage(
                content=[TextBlock(text="Done")],
                model="claude-sonnet-4",
                parent_tool_use_id=None,
            )
            yield ResultMessage(
                subtype="complete",
                duration_ms=100,
                duration_api_ms=80,
                is_error=False,
                num_turns=1,
                session_id="session-2",
            )

        mock_sdk_client.receive_response = mock_receive_response

        client = ClaudeClient()
        messages = []
        async for message in client.stream("test"):
            messages.append(message)

        assert len(messages) == 2
        assert isinstance(messages[0], AssistantMessage)
        assert isinstance(messages[1], ResultMessage)

    @pytest.mark.asyncio
    async def test_grace_period_waits_for_task_completion(self):
        """Verify the grace period logic: wait_for is used instead of immediate cancel
        when the task is not yet done."""
        flush_completed = asyncio.Event()

        async def background():
            await asyncio.sleep(0.05)
            flush_completed.set()

        task = asyncio.create_task(background())
        # Ensure task has started but not completed
        await asyncio.sleep(0)
        assert not task.done()

        # Simulate the stream() finally block logic for early consumer exit
        if not task.done():
            try:
                await asyncio.wait_for(task, timeout=10.0)
            except TimeoutError:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            except asyncio.CancelledError:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        assert flush_completed.is_set(), "Task should complete within grace period instead of being cancelled"

    @pytest.mark.asyncio
    async def test_grace_period_timeout_falls_back_to_cancel(self):
        """Verify that if the task doesn't complete within the grace period,
        it falls back to cancellation."""
        task_was_cancelled = asyncio.Event()

        async def hanging_background():
            try:
                await asyncio.sleep(999)
            except asyncio.CancelledError:
                task_was_cancelled.set()
                raise

        task = asyncio.create_task(hanging_background())
        await asyncio.sleep(0)
        assert not task.done()

        # Simulate the stream() finally block logic with a short timeout
        if not task.done():
            try:
                await asyncio.wait_for(task, timeout=0.1)
            except TimeoutError:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            except asyncio.CancelledError:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        assert task_was_cancelled.is_set(), "Task should be cancelled after grace period timeout"

    @pytest.mark.asyncio
    async def test_completed_task_not_cancelled(self):
        """Verify that an already-completed task is not cancelled."""

        async def quick_background():
            pass

        task = asyncio.create_task(quick_background())
        await task  # Wait for completion

        assert task.done()

        # Simulate the stream() finally block logic — should take the else branch
        cancelled = False
        if not task.done():
            cancelled = True
        else:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        assert not cancelled, "Completed task should not be cancelled"


class TestWaitForSubprocessFlush:
    """Tests for ClaudeClient._wait_for_subprocess_flush."""

    @pytest.mark.asyncio
    async def test_calls_end_input_and_waits_for_process(self):
        """Verify it calls end_input() and process.wait() with timeout."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.wait = AsyncMock()

        mock_transport = AsyncMock()
        mock_transport.end_input = AsyncMock()
        mock_transport._process = mock_process

        mock_query = Mock()
        mock_query.transport = mock_transport

        mock_client = Mock(spec=[])
        mock_client._query = mock_query

        await ClaudeClient._wait_for_subprocess_flush(mock_client, timeout=3.0)

        mock_transport.end_input.assert_awaited_once()
        mock_process.wait.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_wait_when_process_already_exited(self):
        """Verify it skips process.wait() when returncode is already set."""
        mock_process = Mock()
        mock_process.returncode = 0

        mock_transport = AsyncMock()
        mock_transport.end_input = AsyncMock()
        mock_transport._process = mock_process

        mock_query = Mock()
        mock_query.transport = mock_transport

        mock_client = Mock(spec=[])
        mock_client._query = mock_query

        await ClaudeClient._wait_for_subprocess_flush(mock_client)

        mock_transport.end_input.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_timeout_prevents_hanging(self):
        """Verify that if process.wait() blocks, the timeout prevents hanging."""
        mock_process = AsyncMock()
        mock_process.returncode = None

        async def hang_forever():
            await asyncio.sleep(999)

        mock_process.wait = hang_forever

        mock_transport = AsyncMock()
        mock_transport.end_input = AsyncMock()
        mock_transport._process = mock_process

        mock_query = Mock()
        mock_query.transport = mock_transport

        mock_client = Mock(spec=[])
        mock_client._query = mock_query

        # Should complete quickly due to timeout, not hang
        await asyncio.wait_for(
            ClaudeClient._wait_for_subprocess_flush(mock_client, timeout=0.1),
            timeout=2.0,
        )

        mock_transport.end_input.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_query_is_noop(self):
        """Verify it returns immediately if _query is not set."""
        mock_client = Mock(spec=[])
        mock_client._query = None

        await ClaudeClient._wait_for_subprocess_flush(mock_client)

    @pytest.mark.asyncio
    async def test_no_transport_is_noop(self):
        """Verify it returns immediately if transport is not set."""
        mock_query = Mock()
        mock_query.transport = None

        mock_client = Mock(spec=[])
        mock_client._query = mock_query

        await ClaudeClient._wait_for_subprocess_flush(mock_client)

    @pytest.mark.asyncio
    async def test_cancellation_deferred_until_after_process_wait(self):
        """Verify that task cancellation does not prevent process.wait() from completing."""
        mock_process = AsyncMock()
        mock_process.returncode = None

        process_waited = asyncio.Event()

        async def wait_briefly():
            await asyncio.sleep(0.05)
            process_waited.set()

        mock_process.wait = wait_briefly

        mock_transport = AsyncMock()
        mock_transport.end_input = AsyncMock()
        mock_transport._process = mock_process

        mock_query = Mock()
        mock_query.transport = mock_transport

        mock_client = Mock(spec=[])
        mock_client._query = mock_query

        task = asyncio.create_task(ClaudeClient._wait_for_subprocess_flush(mock_client, timeout=2.0))
        await asyncio.sleep(0)  # Let task start
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        assert process_waited.is_set(), "process.wait() should complete even when task is cancelled"
