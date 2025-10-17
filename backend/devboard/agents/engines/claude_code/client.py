"""Claude Code client using claude-agent-sdk for Claude Code CLI integration."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

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
    from claude_agent_sdk.types import StreamEvent
except ImportError:
    StreamEvent = None  # type: ignore


@dataclass
class ClaudeCodeResult:
    """Result from a Claude Code client run."""

    text_content: str
    result_message: ResultMessage
    session_id: str


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
        tools: list[Callable[[dict[str, Any]], Any]] | None = None,
        allowed_tools: list[str] | None = None,
        model: str | None = None,
        cwd: str | None = None,
        plan_mode: bool = False,
    ):
        """Initialize Claude Code client.

        Args:
            session_id: Optional session ID to resume a previous conversation
            system_prompt: Optional system prompt to include in all runs
            tools: Optional list of async Python functions to expose as tools.
                   Each function should accept keyword arguments matching its signature
                   and return a string or dict with 'content' key containing the response.
            allowed_tools: Optional list of allowed tool names (e.g., ["Read", "Bash", "Grep"]).
                           If tools are provided, this will be extended with the custom tool names.
            model: Optional model to use (e.g., "claude-sonnet-4-5-20250929")
            cwd: Optional working directory for Claude Code operations
        """
        # Build options with custom tools if provided
        self.options = self._build_options(
            tools=tools or [],
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            model=model,
            cwd=cwd,
            session_id=session_id,
            plan_mode=plan_mode,
        )
        self.session_id = session_id

    def _build_options(
        self,
        tools: list[Callable[[dict[str, Any]], Any]],
        system_prompt: str | None,
        allowed_tools: list[str] | None,
        model: str | None,
        cwd: str | None,
        session_id: str | None,
        plan_mode: bool = False,
    ) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions from client configuration.

        Args:
            tools: List of Python functions to expose as custom tools
            system_prompt: Optional system prompt suffix
            allowed_tools: Optional list of allowed tool names
            model: Optional model name
            cwd: Optional working directory
            session_id: Optional session ID for resumption

        Returns:
            Configured ClaudeAgentOptions instance
        """
        # Prepare MCP servers and tool names if custom tools are provided
        mcp_servers = None
        final_allowed_tools = allowed_tools

        if tools:
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

            # Combine allowed_tools with custom tool names
            if allowed_tools:
                final_allowed_tools = allowed_tools + custom_tool_names
            else:
                final_allowed_tools = custom_tool_names

        return ClaudeAgentOptions(
            resume=session_id,
            system_prompt=system_prompt,
            allowed_tools=final_allowed_tools,
            model=model,
            cwd=cwd,
            mcp_servers=mcp_servers,
            permission_mode="plan" if plan_mode else "acceptEdits",
        )

    @staticmethod
    def _create_tool_wrapper(func: Callable[..., Any], func_schema: Any) -> Callable[[dict[str, Any]], Any]:
        """Create a wrapper function that converts a regular function to Claude Code tool format.

        Args:
            func: The original function to wrap
            func_schema: The FunctionSchema containing validation and metadata

        Returns:
            An async function that accepts a dict of arguments and returns a dict with 'content' key
        """

        async def wrapper(args: dict[str, Any]) -> dict[str, Any]:
            # Validate arguments using the function schema
            validated_args = func_schema.validator.validate_python(args)

            # Call the original function
            if func_schema.is_async:
                result = await func(**validated_args)
            else:
                result = func(**validated_args)

            # Convert result to Claude Code format
            if isinstance(result, dict) and "content" in result:
                return result
            elif isinstance(result, str):
                return {"content": [{"type": "text", "text": result}]}
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
