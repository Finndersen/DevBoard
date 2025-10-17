"""Claude Code client using claude-agent-sdk for Claude Code CLI integration."""

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
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    tool,
)
from pydantic.json_schema import GenerateJsonSchema
from pydantic_ai._function_schema import function_schema

# StreamEvent is not exported from public API, import from types module
try:
    from claude_agent_sdk.types import StreamEvent, SystemPromptPreset
except ImportError:
    StreamEvent = None  # type: ignore


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


# Type alias for custom tool functions - can be sync or async functions returning str
ClaudeCodeToolFunc = Callable[..., str | Awaitable[str]]


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

    def __init__(
        self,
        session_id: str | None = None,
        system_prompt: str | None = None,
        include_builtin_system_prompt: bool = False,
        tools: list[ClaudeCodeToolFunc] | None = None,
        allowed_builtin_tools: list[str] | None = None,
        model: str | None = None,
        cwd: str | None = None,
        plan_mode: bool = False,
        include_claude_md: bool = False,
    ):
        """Initialize Claude Code client.

        Args:
            session_id: Optional session ID to resume a previous conversation
            system_prompt: Optional system prompt to include in all runs
            include_builtin_system_prompt: Whether to include the built-in system prompt
            tools: Optional list of sync or async Python functions to expose as tools.
                   Each function should accept keyword arguments matching its signature
                   and return a string result.
            allowed_builtin_tools: Optional list of allowed tool names (e.g., ["Read", "Bash", "Grep"]).
                           If tools are provided, this will be extended with the custom tool names.
            model: Optional model to use (e.g., "claude-sonnet-4-5-20250929")
            cwd: Optional working directory for Claude Code operations
            include_claude_md: Whether to load CLAUDE.md prompt guidance files
        """
        self.session_id = session_id

        # Build MCP servers from custom tools if provided
        if tools:
            mcp_servers, custom_tool_names = self._build_mcp_servers(tools)
        else:
            mcp_servers = None
            custom_tool_names = []

        # Combine allowed_tools with custom tool names
        final_allowed_tools = allowed_builtin_tools
        if custom_tool_names:
            if allowed_builtin_tools:
                final_allowed_tools = allowed_builtin_tools + custom_tool_names
            else:
                final_allowed_tools = custom_tool_names

        # Initialize ClaudeAgentOptions directly
        self.options = ClaudeAgentOptions(
            resume=session_id,
            system_prompt=self._build_system_prompt(system_prompt, include_builtin_system_prompt),
            allowed_tools=final_allowed_tools,
            model=model,
            cwd=cwd,
            mcp_servers=mcp_servers,
            permission_mode="plan" if plan_mode else "acceptEdits",
            setting_sources=["user", "project", "local"] if include_claude_md else None,
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
        tools: list[ClaudeCodeToolFunc],
    ) -> tuple[dict[str, Any], list[str]]:
        """Build MCP servers from custom Python tools.

        Args:
            tools: List of sync or async Python functions to expose as custom tools

        Returns:
            Tuple of (mcp_servers dict or None, list of custom tool names)
        """
        # Wrap tools with SDK's @tool decorator
        sdk_tools = []
        custom_tool_names = []

        for tool_func in tools:
            # Use PydanticAI's function_schema to extract metadata
            schema = function_schema(
                function=tool_func,
                schema_generator=GenerateJsonSchema,
                takes_ctx=False,
                docstring_format="auto",
            )

            # Extract function metadata
            tool_name = tool_func.__name__
            tool_description = schema.description or f"Tool: {tool_name}"
            input_schema = schema.json_schema

            # Create wrapper that converts the function to Claude Code format
            wrapper_func = self._create_tool_wrapper(tool_func, schema)

            # Wrap with the @tool decorator
            sdk_tool = tool(tool_name, tool_description, input_schema)(wrapper_func)
            sdk_tools.append(sdk_tool)
            custom_tool_names.append(f"mcp__devboard_tools__{tool_name}")

        # Create SDK MCP server with custom tools
        mcp_server = create_sdk_mcp_server(
            name="devboard_tools",
            version="1.0.0",
            tools=sdk_tools,
        )
        mcp_servers = {"devboard_tools": mcp_server}

        return mcp_servers, custom_tool_names

    @staticmethod
    def _create_tool_wrapper(
        func: ClaudeCodeToolFunc, func_schema: Any
    ) -> Callable[[dict[str, Any]], Awaitable[ClaudeToolContent]]:
        """Create a wrapper function that converts a sync/async function to Claude Code tool format.

        Args:
            func: The original sync or async function to wrap (should return str)
            func_schema: The FunctionSchema containing validation and metadata

        Returns:
            An async function that accepts a dict of arguments and returns ClaudeToolContent
        """

        async def wrapper(args: dict[str, Any]) -> ClaudeToolContent:
            # Validate arguments using the function schema
            validated_args = func_schema.validator.validate_python(args)

            # Call the original function
            if func_schema.is_async:
                result = await func(**validated_args)
            else:
                result = func(**validated_args)

            # Convert result to Claude Code format
            if isinstance(result, dict) and "content" in result:
                return result  # type: ignore[return-value]
            else:
                return {"content": [{"type": "text", "text": str(result)}]}

        return wrapper

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
            query_preview=user_query[:100] if len(user_query) > 100 else user_query,
        ):
            async with ClaudeSDKClient(options=self.options) as client:
                # Send the query
                with logfire.span("claude_client.send_query"):
                    await client.query(user_query)

                async for message in client.receive_response():
                    message_desc = self._describe_message(message)
                    with logfire.span(f"Received message: {message_desc}", message=message):
                        yield message
