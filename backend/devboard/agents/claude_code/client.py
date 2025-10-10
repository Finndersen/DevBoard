"""Claude Code client using claude-agent-sdk for Claude Code CLI integration."""

import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    Message,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)
from pydantic.json_schema import GenerateJsonSchema
from pydantic_ai._function_schema import function_schema

logger = logging.getLogger(__name__)


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
        text_parts: list[str] = []

        async with ClaudeSDKClient(options=self.options) as client:
            # Send the query
            await client.query(user_query)

            # Collect all messages until ResultMessage
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    # Extract text content from assistant messages
                    for content_block in message.content:
                        if isinstance(content_block, TextBlock):
                            text_parts.append(content_block.text)

                elif isinstance(message, ResultMessage):
                    # Combine all text parts
                    combined_text = "\n".join(text_parts) if text_parts else ""
                    return ClaudeCodeResult(
                        text_content=combined_text,
                        result_message=message,
                        session_id=message.session_id,
                    )

        raise RuntimeError("No ResultMessage received from Claude Code")

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

        async with ClaudeSDKClient(options=self.options) as client:
            # Send the query
            await client.query(user_query)

            # Stream messages as they arrive
            async for message in client.receive_response():
                yield message
