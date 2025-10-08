"""Claude Code Agent using claude-agent-sdk for Claude Code CLI integration."""

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

from devboard.agents.types import AgentType

logger = logging.getLogger(__name__)


@dataclass
class ClaudeCodeResult:
    """Result from a Claude Code agent run."""

    text_content: str
    result_message: ResultMessage
    session_id: str


class ClaudeCodeAgent:
    """Agent wrapping ClaudeSDKClient for Claude Code CLI integration.

    This agent provides access to Claude Code's full capabilities including
    file operations, shell commands, and other developer tools through the
    claude-agent-sdk.

    Supports:
    - Session resumption for continuing previous conversations
    - Custom tool registration via Python functions
    - Streaming and non-streaming execution modes
    """

    agent_type = AgentType.CLAUDE_CODE

    def __init__(
        self,
        session_id: str | None = None,
        tools: list[Callable[[dict[str, Any]], Any]] | None = None,
    ):
        """Initialize Claude Code agent.

        Args:
            session_id: Optional session ID to resume a previous conversation
            tools: Optional list of async Python functions to expose as tools.
                   Each function should accept a dict of arguments and return
                   a dict with 'content' key containing the response.
        """
        self.session_id = session_id
        self.options = self._build_options(tools or [])

    def _build_options(self, tools: list[Callable[[dict[str, Any]], Any]]) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions from agent configuration."""
        options = ClaudeAgentOptions()

        # Configure session resumption
        if self.session_id:
            options.resume = self.session_id

        # Configure custom tools if provided
        if tools:
            # Wrap tools with SDK's @tool decorator
            sdk_tools = []
            allowed_tool_names = []

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
                allowed_tool_names.append(f"mcp__devboard_tools__{tool_name}")

            # Create SDK MCP server with custom tools
            mcp_server = create_sdk_mcp_server(
                name="devboard_tools",
                version="1.0.0",
                tools=sdk_tools,
            )

            # Configure options with MCP server and allowed tools
            options.mcp_servers = {"devboard_tools": mcp_server}
            options.allowed_tools = allowed_tool_names

        return options

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
        final_result: ResultMessage | None = None
        final_session_id = self.session_id or "default"

        async with ClaudeSDKClient(options=self.options) as client:
            # Send the query
            await client.query(user_query, session_id=final_session_id)

            # Collect all messages until ResultMessage
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    # Extract text content from assistant messages
                    for content_block in message.content:
                        if isinstance(content_block, TextBlock):
                            text_parts.append(content_block.text)

                elif isinstance(message, ResultMessage):
                    final_result = message
                    final_session_id = message.session_id
                    break

        # Combine all text parts
        combined_text = "\n".join(text_parts) if text_parts else ""

        if final_result is None:
            raise RuntimeError("No ResultMessage received from Claude Code")

        # Set session ID so subsequent runs can resume the conversation
        if not self.session_id:
            self.session_id = final_session_id

        return ClaudeCodeResult(
            text_content=combined_text,
            result_message=final_result,
            session_id=final_session_id,
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
        session_id = self.session_id or "default"

        async with ClaudeSDKClient(options=self.options) as client:
            # Send the query
            await client.query(user_query, session_id=session_id)

            # Stream messages as they arrive
            async for message in client.receive_response():
                if not self.session_id and isinstance(message, ResultMessage):
                    # Set session ID so subsequent runs can resume the conversation
                    self.session_id = message.session_id
                yield message
