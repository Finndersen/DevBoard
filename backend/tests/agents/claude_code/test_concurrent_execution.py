"""Tests for concurrent tool execution in ClaudeClient."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from claude_agent_sdk import ToolUseBlock
from pydantic_ai import Tool

from devboard.agents.engines.claude_code.client import ClaudeClient, ClaudeToolContent
from devboard.agents.engines.claude_code.utils import normalize_tool_name


@pytest.fixture
def mock_tool() -> Tool:
    """Create a mock PydanticAI Tool for testing."""
    tool = Mock(spec=Tool)
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.function_schema = Mock()
    tool.function_schema.json_schema = {"type": "object", "properties": {}}
    tool.function_schema.validator = Mock()
    tool.function_schema.validator.validate_python = Mock(side_effect=lambda x: x)
    tool.function_schema.call = AsyncMock(return_value="test result")
    return tool


@pytest.fixture
def client_with_tools(mock_tool: Tool) -> ClaudeClient:
    """Create a ClaudeClient with mock tools for testing."""
    return ClaudeClient(
        tools=[mock_tool],
        enable_concurrent_execution=True,
        load_settings=False,
    )


class TestConcurrentExecution:
    """Tests for concurrent tool execution functionality."""

    @pytest.mark.asyncio
    async def test_find_tool_by_name(self, client_with_tools: ClaudeClient, mock_tool: Tool) -> None:
        """Test finding a tool by name."""
        # Find tool by exact name
        found_tool = client_with_tools._find_tool_by_name("test_tool")
        assert found_tool == mock_tool

        # Find tool by MCP-prefixed name
        found_tool = client_with_tools._find_tool_by_name("mcp__builtin_tools__test_tool")
        assert found_tool == mock_tool

        # Tool not found
        found_tool = client_with_tools._find_tool_by_name("nonexistent_tool")
        assert found_tool is None

    @pytest.mark.asyncio
    async def test_execute_tool_concurrently(self, client_with_tools: ClaudeClient, mock_tool: Tool) -> None:
        """Test executing a tool concurrently."""
        result = await client_with_tools._execute_tool_concurrently(
            tool=mock_tool,
            tool_args={"arg1": "value1"},
        )

        # Verify the result format
        assert isinstance(result, dict)
        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"
        assert "test result" in result["content"][0]["text"]

        # Verify the tool was called
        mock_tool.function_schema.call.assert_called_once_with({"arg1": "value1"}, ctx=None)

    @pytest.mark.asyncio
    async def test_execute_tool_concurrently_not_found(self, client_with_tools: ClaudeClient) -> None:
        """Test launching concurrent execution for a tool that doesn't exist - should log warning and return early."""
        # Create a ToolUseBlock with nonexistent tool name
        tool_block = ToolUseBlock(id="tool_1", name="nonexistent", input={})

        # Should not raise, just log warning and return early (no task created)
        await client_with_tools._execute_concurrent_mcp_tool(tool_block)

        # Verify no task was added to cache
        assert "tool_1" not in client_with_tools._tool_execution_cache

    @pytest.mark.asyncio
    async def test_execute_tool_concurrently_with_error(self, client_with_tools: ClaudeClient, mock_tool: Tool) -> None:
        """Test concurrent execution when tool raises an error."""
        mock_tool.function_schema.call.side_effect = RuntimeError("Tool execution failed")

        with pytest.raises(RuntimeError, match="Tool execution failed"):
            await client_with_tools._execute_tool_concurrently(
                tool=mock_tool,
                tool_args={},
            )

    @pytest.mark.asyncio
    async def test_launch_concurrent_tool_execution(self, client_with_tools: ClaudeClient, mock_tool: Tool) -> None:
        """Test launching concurrent execution for a single MCP tool."""
        # Create a ToolUseBlock with MCP tool name
        tool_block = ToolUseBlock(id="tool_1", name="mcp__builtin_tools__test_tool", input={"arg": "value1"})

        # Launch concurrent execution
        await client_with_tools._execute_concurrent_mcp_tool(tool_block)

        # Verify task was created and cached
        assert len(client_with_tools._tool_execution_cache) == 1
        assert "tool_1" in client_with_tools._tool_execution_cache

        # Verify queue was populated
        assert client_with_tools._tool_execution_queue.qsize() == 1

        # Wait for execution to complete
        result = await client_with_tools._tool_execution_cache["tool_1"]
        assert isinstance(result, dict)
        assert "content" in result

    @pytest.mark.asyncio
    async def test_launch_concurrent_tool_execution_multiple(
        self, client_with_tools: ClaudeClient, mock_tool: Tool
    ) -> None:
        """Test launching concurrent executions for multiple MCP tools."""
        # Create multiple ToolUseBlocks with MCP tool names
        tool_blocks = [
            ToolUseBlock(id="tool_1", name="mcp__builtin_tools__test_tool", input={"arg": "value1"}),
            ToolUseBlock(id="tool_2", name="mcp__builtin_tools__test_tool", input={"arg": "value2"}),
            ToolUseBlock(id="tool_3", name="mcp__builtin_tools__test_tool", input={"arg": "value3"}),
        ]

        # Launch concurrent executions for each block
        for block in tool_blocks:
            await client_with_tools._execute_concurrent_mcp_tool(block)

        # Verify tasks were created and cached
        assert len(client_with_tools._tool_execution_cache) == 3
        assert "tool_1" in client_with_tools._tool_execution_cache
        assert "tool_2" in client_with_tools._tool_execution_cache
        assert "tool_3" in client_with_tools._tool_execution_cache

        # Verify queue was populated
        assert client_with_tools._tool_execution_queue.qsize() == 3

        # Wait for all executions to complete
        results = await asyncio.gather(*list(client_with_tools._tool_execution_cache.values()))
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_tool_wrapper_returns_cached_result(self, client_with_tools: ClaudeClient, mock_tool: Tool) -> None:
        """Test that tool wrapper returns cached result when available."""
        # Pre-populate cache with a result
        tool_use_id = "test_id_1"
        cached_result: ClaudeToolContent = {"content": [{"type": "text", "text": "cached result"}]}
        future: asyncio.Future[ClaudeToolContent] = asyncio.Future()
        future.set_result(cached_result)
        client_with_tools._tool_execution_cache[tool_use_id] = future

        # Add to queue
        await client_with_tools._tool_execution_queue.put(("test_tool", tool_use_id))

        # Create result retrieval wrapper and call it
        wrapper = client_with_tools._create_tool_result_retrieval_func(mock_tool)
        result = await wrapper({"arg": "value"})

        # Verify cached result was returned
        assert result == cached_result

        # Verify tool was NOT called (because result was cached)
        mock_tool.function_schema.call.assert_not_called()

        # Verify cache was cleaned up
        assert tool_use_id not in client_with_tools._tool_execution_cache

    @pytest.mark.asyncio
    async def test_tool_wrapper_with_empty_queue(self, client_with_tools: ClaudeClient, mock_tool: Tool) -> None:
        """Test that result retrieval wrapper raises an error when queue is empty."""
        # Don't populate queue - should raise an error when trying to get from empty queue

        # Create result retrieval wrapper and call it
        wrapper = client_with_tools._create_tool_result_retrieval_func(mock_tool)

        # Should block waiting for queue item
        # Since we're using asyncio.Queue.get(), it will block indefinitely
        # We need to test with a timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(wrapper({"arg": "value"}), timeout=0.1)

    @pytest.mark.asyncio
    async def test_tool_wrapper_handles_name_mismatch(self, client_with_tools: ClaudeClient, mock_tool: Tool) -> None:
        """Test that result retrieval wrapper raises error on tool name mismatch."""
        # Add wrong tool name to queue
        await client_with_tools._tool_execution_queue.put(("wrong_tool", "test_id"))

        # Create result retrieval wrapper and call it
        wrapper = client_with_tools._create_tool_result_retrieval_func(mock_tool)

        # Should raise RuntimeError due to name mismatch
        with pytest.raises(RuntimeError, match="Tool name mismatch"):
            await wrapper({"arg": "value"})

    @pytest.mark.asyncio
    async def test_is_mcp_tool(self, client_with_tools: ClaudeClient) -> None:
        """Test MCP tool detection."""
        assert ClaudeClient._is_mcp_tool("mcp__builtin_tools__test_tool") is True
        assert ClaudeClient._is_mcp_tool("mcp__other__tool") is True
        assert ClaudeClient._is_mcp_tool("not_mcp_tool") is False
        assert ClaudeClient._is_mcp_tool("Read") is False
        assert ClaudeClient._is_mcp_tool("") is False

    @pytest.mark.asyncio
    async def test_skip_non_mcp_tools(self, client_with_tools: ClaudeClient, mock_tool: Tool) -> None:
        """Test that non-MCP tools are skipped in _start_running_any_mcp_tools."""
        from claude_agent_sdk import AssistantMessage

        # Create an AssistantMessage with non-MCP tool (built-in tool)
        non_mcp_block = ToolUseBlock(id="tool_1", name="Read", input={"file_path": "/test"})
        mcp_block = ToolUseBlock(id="tool_2", name="mcp__builtin_tools__test_tool", input={"arg": "value"})

        message = AssistantMessage(content=[non_mcp_block, mcp_block], model="test-model")

        # Process the message
        await client_with_tools._start_running_any_mcp_tools(message)

        # Verify only MCP tool was cached (non-MCP tool should be skipped)
        assert len(client_with_tools._tool_execution_cache) == 1
        assert "tool_2" in client_with_tools._tool_execution_cache
        assert "tool_1" not in client_with_tools._tool_execution_cache

    @pytest.mark.asyncio
    async def test_normalize_tool_name(self, client_with_tools: ClaudeClient) -> None:
        """Test normalizing tool names - only strips builtin_tools prefix."""
        assert normalize_tool_name("mcp__builtin_tools__test_tool") == "test_tool"
        assert normalize_tool_name("mcp__other__my_tool") == "mcp__other__my_tool"
        assert normalize_tool_name("test_tool") == "test_tool"

    @pytest.mark.asyncio
    async def test_concurrent_execution_disabled(self, mock_tool: Tool) -> None:
        """Test that concurrent execution can be disabled."""
        from claude_agent_sdk import AssistantMessage

        client = ClaudeClient(
            tools=[mock_tool],
            enable_concurrent_execution=False,
            load_settings=False,
        )

        # Create an AssistantMessage with MCP tool
        tool_block = ToolUseBlock(id="tool_1", name="mcp__builtin_tools__test_tool", input={"arg": "value"})
        message = AssistantMessage(content=[tool_block], model="test-model")

        # Process message (should do nothing because concurrent execution is disabled)
        await client._start_running_any_mcp_tools(message)

        # Verify nothing was cached (because feature is disabled)
        assert len(client._tool_execution_cache) == 0

        # Execution wrapper should execute directly
        wrapper = client._create_tool_execution_wrapper(mock_tool, validate_args=True)
        result = await wrapper({"arg": "value"})
        assert isinstance(result, dict)
        mock_tool.function_schema.call.assert_called_once()


class TestConcurrentExecutionIntegration:
    """Integration tests for concurrent execution with message streaming."""

    @pytest.mark.skip(reason="Requires full ClaudeSDKClient mocking - implement after basic tests pass")
    async def test_stream_launches_concurrent_executions(self, client_with_tools: ClaudeClient) -> None:
        """Test that stream() launches concurrent executions for AssistantMessages."""
        # TODO: Mock ClaudeSDKClient and client.receive_response()
        # to return AssistantMessages with ToolUseBlocks
        pass

    @pytest.mark.skip(reason="Requires full ClaudeSDKClient mocking - implement after basic tests pass")
    async def test_concurrent_execution_performance(self, client_with_tools: ClaudeClient) -> None:
        """Test that concurrent execution actually improves performance."""
        # TODO: Create multiple slow tools and verify they run in parallel
        pass
