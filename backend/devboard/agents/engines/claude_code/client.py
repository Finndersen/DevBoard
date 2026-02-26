"""Claude Code client using claude-agent-sdk for Claude Code CLI integration."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypedDict

import logfire
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    Message,
    ResultMessage,
    ToolUseBlock,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk.types import McpSdkServerConfig, PermissionMode, SystemPromptPreset
from pydantic_ai import Tool
from pydantic_core import ValidationError

from .utils import BUILTIN_TOOLS_MCP_NAME, describe_message, load_env_from_settings, normalize_tool_name

# All Claude Code builtin tools
CLAUDE_BUILTIN_TOOLS: set[str] = {
    # File Operations
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
    "NotebookEdit",
    # Execution
    "Bash",
    "Task",
    "Skill",
    # Planning & Task Management
    "EnterPlanMode",
    "ExitPlanMode",
    "TodoWrite",
    # User Interaction
    "AskUserQuestion",
    # Web
    "WebFetch",
    "WebSearch",
}


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

    Supports:
    - Session resumption for continuing previous conversations
    - Custom tool registration via PydanticAI Tool instances
    - Custom system prompts
    - Tool filtering via allowed_builtin_tools
    - Streaming and non-streaming execution modes
    - Parallel tool execution for concurrent tool calls
    """

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

        # Validate allowed_builtin_tools
        if allowed_builtin_tools:
            invalid_tools = set(allowed_builtin_tools) - CLAUDE_BUILTIN_TOOLS
            if invalid_tools:
                raise ValueError(f"Invalid builtin tool names: {invalid_tools}. Valid tools: {CLAUDE_BUILTIN_TOOLS}")

        # Both allowed_tools and disallowed_tools are required to both allow needed tools, but also hide remaining tools
        # Calculate disallowed tools (all builtin tools minus allowed ones)
        # Custom MCP tools are always allowed - they are not part of the disallowed calculation
        allowed_set: set[str] = set(allowed_builtin_tools) if allowed_builtin_tools else set()
        disallowed_tools = list(CLAUDE_BUILTIN_TOOLS - allowed_set)

        # Build MCP server from custom tools if provided
        if tools:
            mcp_server_config, custom_tool_names = self._build_custom_tools_mcp_server(tools)
            mcp_servers = {mcp_server_config["name"]: mcp_server_config}
        else:
            mcp_servers = None
            custom_tool_names = []

        # Combine allowed builtin tools with custom MCP tool names
        all_allowed_tools = list(allowed_set) + custom_tool_names

        # Load environment variables from user settings
        env_vars = load_env_from_settings()
        # Set model name when using AWS Bedrock
        if model and env_vars.get("CLAUDE_CODE_USE_BEDROCK") == "1":
            region_prefix = env_vars.get("AWS_REGION", "us-west-1").split("-")[0]
            model = f"{region_prefix}.anthropic.{model}-v1:0"

        # Initialize ClaudeAgentOptions directly
        permission_mode: PermissionMode
        if plan_mode:
            permission_mode = "plan"
        elif "Write" in all_allowed_tools:
            permission_mode = "acceptEdits"
        else:
            permission_mode = "default"

        self.options = ClaudeAgentOptions(
            resume=session_id,
            system_prompt=self._build_system_prompt(system_prompt, include_builtin_system_prompt),
            allowed_tools=all_allowed_tools,
            disallowed_tools=disallowed_tools,
            model=model,
            cwd=cwd,
            mcp_servers=mcp_servers,
            permission_mode=permission_mode,
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

    def _build_custom_tools_mcp_server(
        self,
        tools: list[Tool],
    ) -> tuple[McpSdkServerConfig, list[str]]:
        """Build an MCP server from PydanticAI Tool instances.

        Args:
            tools: List of PydanticAI Tool instances

        Returns:
            Tuple of (MCP server config, list of custom tool names for allowed_tools)
        """
        # Wrap tools with SDK's @tool decorator
        sdk_tools = []
        custom_tool_names = []
        for pydantic_tool in tools:
            # Extract metadata from PydanticAI Tool's function_schema
            tool_name = pydantic_tool.name

            # Create wrapper that converts the function to Claude Code format
            if self._enable_concurrent_execution:
                wrapper_func = self._create_tool_result_retrieval_func(pydantic_tool)
            else:
                wrapper_func = self._create_tool_execution_wrapper(pydantic_tool, validate_args=True)

            # Wrap with the @tool decorator
            sdk_tool = tool(
                name=tool_name,
                description=pydantic_tool.description,
                input_schema=pydantic_tool.function_schema.json_schema,
            )(wrapper_func)
            sdk_tools.append(sdk_tool)
            custom_tool_names.append(f"mcp__{BUILTIN_TOOLS_MCP_NAME}__{tool_name}")

        # Create SDK MCP server with custom tools
        mcp_server_config = create_sdk_mcp_server(
            name=BUILTIN_TOOLS_MCP_NAME,
            version="1.0.0",
            tools=sdk_tools,
        )
        return mcp_server_config, custom_tool_names

    def _create_tool_execution_wrapper(
        self,
        pydantic_tool: Tool,
        *,
        validate_args: bool,
    ) -> Callable[[dict[str, Any]], Awaitable[ClaudeToolContent]]:
        """Create a wrapper function that converts a PydanticAI Tool to Claude Code tool format.

        Args:
            pydantic_tool: PydanticAI Tool instance

        Returns:
            An async function that accepts a dict of arguments and returns ClaudeToolContent
        """

        async def normal_wrapper(args: dict[str, Any]) -> ClaudeToolContent:
            with logfire.span(
                f"Calling tool: {pydantic_tool.name}()",
                tool_name=pydantic_tool.name,
                args=args,
            ):
                if validate_args:
                    # Validate arguments using the tool's schema validator
                    validated_args = pydantic_tool.function_schema.validator.validate_python(args)
                else:
                    validated_args = args

                result = await pydantic_tool.function_schema.call(validated_args, ctx=None)

                # Convert result to Claude Code format
                if isinstance(result, dict) and "content" in result:
                    return result  # type: ignore[return-value]
                else:
                    return {"content": [{"type": "text", "text": str(result)}]}

        return normal_wrapper

    def _create_tool_result_retrieval_func(
        self,
        pydantic_tool: Tool,
    ) -> Callable[[dict[str, Any]], Awaitable[ClaudeToolContent]]:
        """
        Create a tool function that does not actually execute the tool but retrieves its result from the tool task.
        :param pydantic_tool:
        :return:
        """

        # Concurrent execution wrapper - returns cached results
        async def retrieve_tool_result(args: dict[str, Any]) -> ClaudeToolContent:
            # Get the tool_use_id from the queue (order-based correlation)
            tool_name_expected, tool_use_id = await self._tool_execution_queue.get()
            with logfire.span(
                f"Retrieving result for tool: {pydantic_tool.name}()",
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

        return retrieve_tool_result

    def _find_tool_by_name(self, tool_name: str) -> Tool | None:
        """Find a tool by its name, handling MCP prefixes.

        Args:
            tool_name: Tool name, possibly with MCP prefix (e.g., "mcp__builtin_tools__search")

        Returns:
            Tool instance if found, None otherwise
        """
        # Remove MCP prefix if present (e.g., "mcp__builtin_tools__search" -> "search")
        clean_name = normalize_tool_name(tool_name)

        for pydantic_tool in self._tools:
            if pydantic_tool.name == clean_name:
                return pydantic_tool
        return None

    async def _execute_tool_concurrently(
        self,
        tool: Tool,
        tool_args: dict[str, Any],
    ) -> ClaudeToolContent:
        """Execute a tool asynchronously so its result can be retrieved later.

        Args:
            tool: PydanticAI Tool instance to execute
            tool_args: Validated input arguments for the tool

        Returns:
            Tool execution result in Claude Code format
        """
        wrapper = self._create_tool_execution_wrapper(tool, validate_args=False)
        formatted_result = await wrapper(tool_args)
        return formatted_result

    async def _execute_concurrent_mcp_tool(self, tool_block: ToolUseBlock) -> None:
        """
        Launch async execution for a single tool use block.
        If tool name or arguments are invalid, do not create a task since the MCP client should also fail validation
        and not actually make the tool call.

        Args:
            tool_block: ToolUseBlock to execute concurrently
        """
        # Find the tool
        tool = self._find_tool_by_name(tool_block.name)
        if not tool:
            logfire.warn(f"Invalid tool name: '{tool_block.name}'", tool_use_id=tool_block.id)
            return

        try:
            validated_args = tool.function_schema.validator.validate_python(tool_block.input)
        except ValidationError as e:
            logfire.warn(f"Invalid arguments for tool '{tool_block.name}'", tool_use_id=tool_block.id, error=e)
            return

        logfire.debug(
            "Launching concurrent execution for tool",
            tool_use_id=tool_block.id,
            tool_name=tool_block.name,
        )

        # Create async task for this tool execution with pre-validated args
        task = asyncio.create_task(
            self._execute_tool_concurrently(
                tool=tool,
                tool_args=validated_args,
            )
        )

        # Cache the task (future) by tool_use_id
        self._tool_execution_cache[tool_block.id] = task

        # Add to queue for order-based correlation
        # Store (tool_name, tool_use_id) so we can match MCP calls
        await self._tool_execution_queue.put((normalize_tool_name(tool_block.name), tool_block.id))

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
        # We use a queue-based approach to decouple the SDK client lifecycle from the
        # generator consumer. This is necessary because:
        #
        # 1. The ClaudeSDKClient uses anyio TaskGroups internally which enforce that
        #    async context managers must be entered and exited in the SAME asyncio task
        #
        # 2. When this async generator yields, control returns to the consumer. If the
        #    consumer stops iterating (e.g., client disconnects, request cancelled),
        #    Python sends GeneratorExit to clean up the generator
        #
        # 3. This cleanup may run in a DIFFERENT task than the one that entered the
        #    async context manager, causing: "RuntimeError: Attempted to exit cancel
        #    scope in a different task than it was entered in"
        #
        # By running the SDK client in its own dedicated task (_consume_sdk), we ensure
        # the same task always handles both __aenter__ and __aexit__, regardless of what
        # happens to the consumer.
        queue: asyncio.Queue[Message | BaseException | None] = asyncio.Queue()

        async def _consume_sdk() -> None:
            """Background task that owns the SDK client lifecycle.

            This task is responsible for:
            - Entering and exiting the ClaudeSDKClient context (same task guarantee)
            - Receiving messages and pushing them to the queue
            - Signaling completion or errors to the consumer via the queue
            """
            try:
                with logfire.span(
                    "claude_client.stream",
                    session_id=self.session_id,
                    model=self.options.model,
                    system_prompt=self.options.system_prompt,
                ):
                    async with ClaudeSDKClient(options=self.options) as client:
                        with logfire.span("claude_client.send_query", query=user_query):
                            await client.query(user_query)

                        async for message in client.receive_response():
                            message_desc = describe_message(message)
                            logfire.info(f"Received message: {message_desc}", message=message)
                            await self._start_running_any_mcp_tools(message)
                            await queue.put(message)
            except Exception as e:
                # Propagate exceptions to the consumer via the queue
                await queue.put(e)
            finally:
                # Signal completion (None sentinel) so consumer knows to stop
                await queue.put(None)

        task = asyncio.create_task(_consume_sdk())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    # SDK task completed normally
                    break
                if isinstance(item, BaseException):
                    # SDK task encountered an error - re-raise in consumer context
                    raise item
                yield item
        finally:
            # If consumer stops early (e.g., client disconnect), cancel the SDK task.
            # The SDK task will handle its own cleanup in its own task context.
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _start_running_any_mcp_tools(self, message: Message):
        # Launch concurrent tool executions if enabled
        if self._enable_concurrent_execution and isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock) and self._is_mcp_tool(block.name):
                    await self._execute_concurrent_mcp_tool(block)

    @staticmethod
    def _is_mcp_tool(tool_name: str) -> bool:
        return "__" in tool_name and tool_name.split("__")[0] == "mcp"
