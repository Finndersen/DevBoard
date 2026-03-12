"""Claude Code client using claude-agent-sdk for Claude Code CLI integration."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypedDict

import logfire
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    Message,
    ResultMessage,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk.types import McpSdkServerConfig, PermissionMode, SystemPromptPreset
from mcp.types import ToolAnnotations
from pydantic_ai import Tool

from .utils import BUILTIN_TOOLS_MCP_NAME, describe_message, load_env_from_settings

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
    "TaskCreate",
    "TaskGet",
    "TaskUpdate",
    "TaskList",
    "Agent",
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
        """
        self.session_id = session_id
        self._tools = tools or []

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
            mcp_servers = {}
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
        else:
            # disallowed_tools deny rules still apply. This enables execution of all enabled MCP server tools
            permission_mode = "bypassPermissions"

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
            stderr=lambda line: logfire.warning("Claude CLI stderr: {line}", line=line),
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
            wrapper_func = self._create_tool_execution_wrapper(pydantic_tool, validate_args=True)

            # Wrap with the @tool decorator
            # readOnlyHint=True signals to the CLI that these tools don't modify their
            # environment, enabling concurrent execution of multiple tool calls.
            # All function tools are read-only by design (write operations go through virtual tools).
            sdk_tool = tool(
                name=tool_name,
                description=pydantic_tool.description,
                input_schema=pydantic_tool.function_schema.json_schema,
                annotations=ToolAnnotations(readOnlyHint=True),
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

                try:
                    result = await pydantic_tool.function_schema.call(validated_args, ctx=None)
                except Exception as e:
                    error_text = f"An error occurred during tool execution: {e}"
                    logfire.exception(
                        f"Tool execution failed: {pydantic_tool.name}",
                        tool_name=pydantic_tool.name,
                        tool_result=error_text,
                    )
                    return {"content": [{"type": "text", "text": error_text}]}

                # Convert result to Claude Code format
                if isinstance(result, dict) and "content" in result:
                    return result  # type: ignore[return-value]
                else:
                    return {"content": [{"type": "text", "text": str(result)}]}

        return normal_wrapper

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

    async def stream(self, user_query: str, interrupt_event: asyncio.Event | None = None) -> AsyncIterator[Message]:
        """Execute a query and stream individual messages as they arrive.

        This method yields messages in real-time, allowing for progressive
        rendering and processing of the response.

        Args:
            user_query: The user's query/prompt to send to Claude Code
            interrupt_event: Optional asyncio.Event; when set, sends a native SDK interrupt signal

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

                        # Spawn interrupt monitor to send native SDK interrupt signal when requested
                        monitor_task: asyncio.Task[None] | None = None
                        if interrupt_event is not None:
                            _interrupt_event = interrupt_event

                            async def _monitor_interrupt() -> None:
                                await _interrupt_event.wait()
                                try:
                                    await client.interrupt()
                                except Exception as e:
                                    logfire.error(f"Failed to interrupt Claude Code session: {e}")

                            monitor_task = asyncio.create_task(_monitor_interrupt())

                        try:
                            async for message in client.receive_response():
                                message_desc = describe_message(message)
                                logfire.info(f"Received message: {message_desc}")
                                await queue.put(message)
                        except asyncio.CancelledError:
                            # Consumer disconnected during streaming.
                            # Don't propagate - this would trigger __aexit__ cleanup that
                            # closes stdin while MCP tool requests are still pending,
                            # causing "Tool permission stream closed" errors in the session.
                            logfire.info("SDK consumer cancelled during streaming")
                        finally:
                            if monitor_task and not monitor_task.done():
                                monitor_task.cancel()
                                with contextlib.suppress(asyncio.CancelledError):
                                    await monitor_task

                        await self._wait_for_subprocess_flush(client)
            except asyncio.CancelledError:
                # Consumer cancelled this task (e.g. client disconnect) before
                # streaming completed. The SDK context exits cleanly via __aexit__.
                pass
            except Exception as e:
                # Propagate exceptions to the consumer via the queue
                await queue.put(e)
            finally:
                with contextlib.suppress(asyncio.CancelledError):
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
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    @staticmethod
    async def _wait_for_subprocess_flush(client: ClaudeSDKClient, timeout: float = 5.0) -> None:
        """Close stdin and wait for the CLI subprocess to flush and exit.

        The SDK's transport.close() sends EOF and SIGTERM almost simultaneously,
        which can kill the subprocess before it finishes writing the session file.
        By closing stdin early and waiting (shielded from cancellation), we let
        the subprocess flush and exit naturally. If this coroutine is cancelled,
        we still wait for the subprocess before returning.
        """
        try:
            query = getattr(client, "_query", None)
            if not query:
                return
            transport = getattr(query, "transport", None)
            if not transport:
                return
            # Wait for any in-flight SDK control request handlers to finish
            # writing responses to the CLI before we close stdin.
            # The SDK Query tracks pending responses in pending_control_responses.
            pending = getattr(query, "pending_control_responses", None)
            if isinstance(pending, dict) and pending:
                logfire.debug(f"Waiting for {len(pending)} pending control responses before closing stdin")
                for _ in range(50):  # Up to 5 seconds (50 * 0.1s)
                    if not pending:
                        break
                    await asyncio.sleep(0.1)

            await transport.end_input()
            process = getattr(transport, "_process", None)
            if process and process.returncode is None:
                wait_task = asyncio.ensure_future(process.wait())
                try:
                    await asyncio.wait_for(asyncio.shield(wait_task), timeout=timeout)
                except asyncio.CancelledError:
                    # Consumer cancelled us while we were waiting for the subprocess.
                    # Wait for it to finish naturally — subprocess flush is the goal,
                    # not propagating the cancellation.
                    with contextlib.suppress(TimeoutError, Exception):
                        await asyncio.wait_for(wait_task, timeout=timeout)
                except TimeoutError:
                    pass
        except (asyncio.CancelledError, Exception):
            # Swallow all errors including CancelledError. Catching CancelledError here
            # is critical: it consumes the cancellation (decrements _num_cancels_requested),
            # so ClaudeSDKClient.__aexit__ can disconnect cleanly without hitting a second
            # CancelledError and producing a cascading exception chain.
            pass
