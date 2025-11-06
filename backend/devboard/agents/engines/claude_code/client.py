"""Claude Code client using claude-agent-sdk for Claude Code CLI integration."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import logfire
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk.types import StreamEvent, SystemPromptPreset
from pydantic import ValidationError
from pydantic_ai import Tool


@dataclass
class ClaudeCodeResult:
    """Result from a Claude Code client run."""

    text_content: str
    result_message: ResultMessage
    session_id: str


class ClaudeToolTextBlock(TypedDict):
    """Text block structure expected by Claude SDK tools."""

    type: str  # Should be "text"
    text: str


class ClaudeToolContent(TypedDict):
    """Content structure expected by Claude SDK tool responses."""

    content: list[ClaudeToolTextBlock]


class ClaudeClient:
    """Low-level client wrapping ClaudeSDKClient for Claude Code CLI integration.

    This client provides a minimal interface to Claude Code's capabilities.
    For application-level agents with tool handling and document editing,
    use BaseClaudeAgent instead.

    Supports:
    - Session resumption for continuing previous conversations
    - Custom tool registration via Python functions
    - Custom system prompts
    - Tool filtering via allowed_tools
    - Streaming and non-streaming execution modes
    """

    @staticmethod
    def _load_env_from_settings() -> dict[str, str]:
        """Load environment variables from ~/.claude/settings.json.

        Returns:
            Dictionary of environment variables, or empty dict if not found
        """
        settings_path = Path.home() / ".claude" / "settings.json"

        if not settings_path.exists():
            return {}

        try:
            with settings_path.open() as f:
                settings = json.load(f)
                return settings.get("env", {})
        except (json.JSONDecodeError, OSError) as e:
            logfire.warn(f"Failed to load Claude settings from {settings_path}: {e}")
            return {}

    def __init__(
        self,
        session_id: str | None = None,
        system_prompt: str | None = None,
        include_builtin_system_prompt: bool = False,
        tools: list[Tool] | None = None,
        allowed_builtin_tools: list[str] | None = None,
        model: str | None = None,
        cwd: str | None = None,
        plan_mode: bool = False,
        load_settings: bool = True,
        enable_concurrent_execution: bool = True,
    ):
        """Initialize Claude Code client.

        Args:
            session_id: Optional session ID to resume a previous conversation
            system_prompt: Optional system prompt to include in all runs
            include_builtin_system_prompt: Whether to include the built-in system prompt
            tools: Optional list of PydanticAI Tool instances to expose as tools.
            allowed_builtin_tools: Optional list of allowed tool names (e.g., ["Read", "Bash", "Grep"]).
            model: Optional model to use (e.g., "claude-sonnet-4-5-20250929")
            cwd: Optional working directory for Claude Code operations
            load_settings: Whether to load local, project and user-level .settings.json and CLAUDE.md files
            enable_concurrent_execution: Enable concurrent execution of multiple tool calls
        """
        self.session_id = session_id
        self._tools = tools or []
        self._enable_concurrent_execution = enable_concurrent_execution

        # Concurrent execution tracking
        self._tool_execution_cache: dict[str, asyncio.Future[ClaudeToolContent]] = {}
        self._tool_execution_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

        # Build MCP servers from custom tools if provided
        if tools:
            mcp_servers, custom_tool_names = self._build_mcp_servers(tools)
        else:
            mcp_servers = None
            custom_tool_names = []

        # Combine allowed_tools with custom tool names
        all_allowed_tools = allowed_builtin_tools or []
        if custom_tool_names:
            all_allowed_tools += custom_tool_names

        # Load environment variables from user settings
        env_vars = self._load_env_from_settings()
        # Set model name when using AWS Bedrock
        if model and env_vars.get("CLAUDE_CODE_USE_BEDROCK") == "1":
            region_prefix = env_vars.get("AWS_REGION", "us-west-1").split("-")[0]
            model = f"{region_prefix}.anthropic.{model}-v1:0"

        # Initialize ClaudeAgentOptions directly
        self.options = ClaudeAgentOptions(
            resume=session_id,
            system_prompt=self._build_system_prompt(system_prompt, include_builtin_system_prompt),
            allowed_tools=all_allowed_tools,
            model=model,
            cwd=cwd,
            mcp_servers=mcp_servers,
            permission_mode="plan" if plan_mode else "default",
            setting_sources=["local", "project", "user"] if load_settings else None,
            env=env_vars,
        )

    def _build_system_prompt(
        self, system_prompt: str | None, include_builtin_system_prompt: bool
    ) -> SystemPromptPreset | str | None:
        if include_builtin_system_prompt:
            if system_prompt:
                return SystemPromptPreset(type="preset", preset="claude_code", append=system_prompt)
            else:
                return SystemPromptPreset(type="preset", preset="claude_code")
        elif system_prompt:
            return system_prompt
        else:
            return None

    def _build_mcp_servers(
        self,
        tools: list[Tool],
    ) -> tuple[dict[str, Any], list[str]]:
        """Build MCP servers from PydanticAI Tool instances.

        Args:
            tools: List of PydanticAI Tool instances

        Returns:
            Tuple of (mcp_servers dict, list of custom tool names)
        """
        # Wrap tools with SDK's @tool decorator
        sdk_tools = []
        custom_tool_names = []
        mcp_name = "builtin_tools"
        for pydantic_tool in tools:
            # Extract metadata from PydanticAI Tool's function_schema
            tool_name = pydantic_tool.name
            tool_description = pydantic_tool.description
            input_schema = pydantic_tool.function_schema.json_schema

            # Create wrapper that converts the function to Claude Code format
            if self._enable_concurrent_execution:
                wrapper_func = self._create_tool_result_retrieval_wrapper(pydantic_tool)
            else:
                wrapper_func = self._create_tool_execution_wrapper(pydantic_tool)

            # Wrap with the @tool decorator
            sdk_tool = tool(tool_name, tool_description, input_schema)(wrapper_func)
            sdk_tools.append(sdk_tool)
            custom_tool_names.append(f"mcp__{mcp_name}__{tool_name}")

        # Create SDK MCP server with custom tools
        mcp_server = create_sdk_mcp_server(
            name=mcp_name,
            version="1.0.0",
            tools=sdk_tools,
        )
        mcp_servers = {mcp_name: mcp_server}

        return mcp_servers, custom_tool_names

    def _create_tool_execution_wrapper(
        self,
        pydantic_tool: Tool,
    ) -> Callable[[dict[str, Any]], Awaitable[ClaudeToolContent]]:
        """Create a wrapper function that converts a PydanticAI Tool to Claude Code tool format.

        Args:
            pydantic_tool: PydanticAI Tool instance

        Returns:
            An async function that accepts a dict of arguments and returns ClaudeToolContent
        """

        async def normal_wrapper(args: dict[str, Any]) -> ClaudeToolContent:
            with logfire.span(
                f"tool.{pydantic_tool.name}",
                tool_name=pydantic_tool.name,
                args=args,
            ):
                try:
                    # Validate arguments using the tool's schema validator
                    validated_args = pydantic_tool.function_schema.validator.validate_python(args)
                    result = await pydantic_tool.function_schema.call(validated_args, ctx=None)

                    # Convert result to Claude Code format
                    if isinstance(result, dict) and "content" in result:
                        return result  # type: ignore[return-value]
                    else:
                        return {"content": [{"type": "text", "text": str(result)}]}
                except ValidationError as e:
                    logfire.error(f"Tool call argument validation error: {e}")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error calling tool: {e}. Check the tool schema and arguments and try again",
                            }
                        ]
                    }

        return normal_wrapper

    def _create_tool_result_retrieval_wrapper(
        self,
        pydantic_tool: Tool,
    ) -> Callable[[dict[str, Any]], Awaitable[ClaudeToolContent]]:
        # Concurrent execution wrapper - returns cached results
        async def result_retrieval_wrapper(args: dict[str, Any]) -> ClaudeToolContent:
            # Get the tool_use_id from the queue (order-based correlation)
            tool_name_expected, tool_use_id = await self._tool_execution_queue.get()
            with logfire.span(
                f"Retrieving {pydantic_tool.name} tool result",
                tool_call_id=tool_use_id,
            ):
                # Verify tool name matches
                if tool_name_expected != pydantic_tool.name:
                    error_msg = (
                        f"Tool name mismatch in MCP call: expected {tool_name_expected}, got {pydantic_tool.name}"
                    )
                    logfire.error(error_msg, tool_use_id=tool_use_id)
                    raise RuntimeError(error_msg)

                # Get cached result
                if tool_use_id not in self._tool_execution_cache:
                    error_msg = f"No cached result found for tool_use_id {tool_use_id}"
                    logfire.error(error_msg, tool_name=pydantic_tool.name)
                    raise RuntimeError(error_msg)

                # Wait for the result (may already be complete)
                result = await self._tool_execution_cache[tool_use_id]

                # Clean up the cache entry
                del self._tool_execution_cache[tool_use_id]

                return result

        return result_retrieval_wrapper

    def _find_tool_by_name(self, tool_name: str) -> Tool | None:
        """Find a tool by its name, handling MCP prefixes.

        Args:
            tool_name: Tool name, possibly with MCP prefix (e.g., "mcp__builtin_tools__search")

        Returns:
            Tool instance if found, None otherwise
        """
        # Remove MCP prefix if present (e.g., "mcp__builtin_tools__search" -> "search")
        clean_name = self._get_original_tool_name_from_mcp_tool(tool_name)

        for tool in self._tools:
            if tool.name == clean_name:
                return tool
        return None

    async def _execute_tool_concurrently(
        self,
        tool_use_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> ClaudeToolContent:
        """Execute a tool asynchronously and cache the result.

        Args:
            tool_use_id: Unique identifier for this tool use
            tool_name: Name of the tool to execute
            tool_input: Input arguments for the tool

        Returns:
            Tool execution result in Claude Code format

        Raises:
            ValueError: If tool is not found
        """
        # Find the tool by name
        tool = self._find_tool_by_name(tool_name)
        if not tool:
            error_msg = f"Tool {tool_name} not found for concurrent execution"
            logfire.error(error_msg, tool_use_id=tool_use_id)
            raise ValueError(error_msg)

        wrapper = self._create_tool_execution_wrapper(tool)
        formatted_result = await wrapper(tool_input)
        return formatted_result

    async def _execute_concurrent_mcp_tool(self, tool_block: ToolUseBlock) -> None:
        """Launch async execution for a single tool use block.

        Args:
            tool_block: ToolUseBlock to execute concurrently
        """
        logfire.debug(
            "Launching concurrent execution for tool",
            tool_use_id=tool_block.id,
            tool_name=tool_block.name,
        )

        # Create async task for this tool execution
        task = asyncio.create_task(
            self._execute_tool_concurrently(
                tool_use_id=tool_block.id,
                tool_name=tool_block.name,
                tool_input=tool_block.input,
            )
        )

        # Cache the task (future) by tool_use_id
        self._tool_execution_cache[tool_block.id] = task

        # Add to queue for order-based correlation
        # Store (tool_name, tool_use_id) so we can match MCP calls
        await self._tool_execution_queue.put(
            (self._get_original_tool_name_from_mcp_tool(tool_block.name), tool_block.id)
        )

    @staticmethod
    def _describe_message(message: Message) -> str:
        """Generate a concise description of a Claude SDK message.

        Args:
            message: The message to describe

        Returns:
            A string describing the message type and its key content
        """
        if isinstance(message, UserMessage):
            # Check if content is a list of blocks or a simple string
            if isinstance(message.content, str):
                return f"UserMessage(text, {len(message.content)} chars)"

            # Analyze content blocks
            text_blocks = sum(1 for block in message.content if isinstance(block, TextBlock))
            tool_results = [block for block in message.content if isinstance(block, ToolResultBlock)]

            parts = []
            if text_blocks:
                parts.append(f"{text_blocks} text")
            if tool_results:
                parts.append(f"{len(tool_results)} tool_result(s)")

            content_desc = ", ".join(parts) if parts else "empty"
            return f"UserMessage({content_desc})"

        elif isinstance(message, AssistantMessage):
            # Analyze content blocks
            text_blocks = sum(1 for block in message.content if isinstance(block, TextBlock))
            thinking_blocks = sum(1 for block in message.content if isinstance(block, ThinkingBlock))
            tool_uses = [block for block in message.content if isinstance(block, ToolUseBlock)]

            parts = []
            if text_blocks:
                parts.append(f"{text_blocks} text")
            if thinking_blocks:
                parts.append(f"{thinking_blocks} thinking")
            if tool_uses:
                tool_names = [tool.name for tool in tool_uses]
                parts.append(f"tools: {', '.join(tool_names)}")

            content_desc = ", ".join(parts) if parts else "empty"
            return f"AssistantMessage({content_desc}, model={message.model})"

        elif isinstance(message, SystemMessage):
            return f"SystemMessage(subtype={message.subtype})"

        elif isinstance(message, ResultMessage):
            status = "error" if message.is_error else "success"
            cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "N/A"
            return f"ResultMessage({status}, cost={cost}, turns={message.num_turns})"

        elif StreamEvent and isinstance(message, StreamEvent):
            event_type = message.event.get("type", "unknown")
            return f"StreamEvent(type={event_type})"

        else:
            return f"Unknown message type: {type(message).__name__}"

    async def run(self, user_query: str) -> ClaudeCodeResult:
        """Execute a query and return a single result.

        This method waits for the complete response and returns a consolidated
        result containing the final text content and metadata.

        Args:
            user_query: The user's query/prompt to send to Claude Code

        Returns:
            ClaudeCodeResult containing the response text, result metadata,
            and session ID for resuming
        """
        result_message = None

        # Collect all messages. The stream automatically terminates after ResultMessage.
        async for message in self.stream(user_query):
            # There may be intermediate AssistantMessages before the final ResultMessage that wont be captured
            if isinstance(message, ResultMessage):
                result_message = message
                # Continue to let iterator finish naturally and ensure cleanup

        if not result_message or result_message.result is None:
            raise RuntimeError("No ResultMessage received from Claude Code")

        return ClaudeCodeResult(
            text_content=result_message.result,
            result_message=result_message,
            session_id=result_message.session_id,
        )

    async def stream(self, user_query: str) -> AsyncIterator[Message]:
        """Execute a query and stream individual messages as they arrive.

        This method yields messages in real-time, allowing for progressive
        rendering and processing of the response.

        Args:
            user_query: The user's query/prompt to send to Claude Code

        Yields:
            Message objects (UserMessage, AssistantMessage, SystemMessage, ResultMessage)
            as they are received from Claude Code
        """
        with logfire.span(
            "claude_client.stream",
            session_id=self.session_id,
            model=self.options.model,
            system_prompt=self.options.system_prompt,
        ):
            async with ClaudeSDKClient(options=self.options) as client:
                # Send the query
                with logfire.span("claude_client.send_query", query=user_query):
                    await client.query(user_query)

                async for message in client.receive_response():
                    message_desc = self._describe_message(message)
                    with logfire.span(f"Received message: {message_desc}", message=message):
                        await self._start_running_any_mcp_tools(message)

                        yield message

    async def _start_running_any_mcp_tools(self, message: Message):
        # Launch concurrent tool executions if enabled
        if self._enable_concurrent_execution and isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock) and self._is_mcp_tool(block.name):
                    await self._execute_concurrent_mcp_tool(block)

    @staticmethod
    def _is_mcp_tool(tool_name: str) -> bool:
        return "__" in tool_name and tool_name.split("__")[0] == "mcp"

    @staticmethod
    def _get_original_tool_name_from_mcp_tool(mcp_tool_name: str) -> str:
        """Get the original tool name from an MCP tool name."""
        return mcp_tool_name.split("__")[-1] if "__" in mcp_tool_name else mcp_tool_name
