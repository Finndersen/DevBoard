"""Base agent class for Claude Code agents with virtual tool calling."""

import asyncio
import datetime
import difflib
from collections.abc import AsyncIterator

import logfire
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
)
from pydantic_ai import ModelRetry, Tool

from devboard.agents.base_agent import BaseAgent
from devboard.agents.engines.claude_code.client import ClaudeClient
from devboard.agents.engines.claude_code.message_converter import (
    InvalidVirtualToolCallError,
    convert_claude_message_to_events,
)
from devboard.agents.engines.claude_code.message_parser import (
    ClaudeResponseParser,
    ToolCallOutcome,
    VirtualToolCall,
    format_tool_result,
)
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionService
from devboard.agents.engines.claude_code.virtual_tools import (
    VirtualTool,
    build_virtual_tool_schemas_section,
)
from devboard.agents.events import (
    ConversationEvent,
    SystemEvent,
    SystemEventType,
    ToolCall,
    ToolResult,
)
from devboard.agents.language_models import LanguageModel, LLMProvider
from devboard.agents.roles.base import AgentRole
from devboard.api.schemas.agent_conversation import (
    ToolApprovals,
)

# Maximum number of retry attempts for invalid responses
MAX_RETRY_ATTEMPTS = 3


def _should_retry_error_result(result: str | None) -> bool:
    """Check if an API error result should trigger a retry.

    Retryable errors include:
    - API 500 errors (server errors)
    - API 400 errors with duplicate tool_use IDs
    - API 400 errors due to tool use concurrency issues
    """
    if not result:
        return False

    if "API Error: 500" in result:
        return True

    if "API Error: 400" in result:
        if "tool_use ids must be unique" in result:
            return True
        if "tool use concurrency issues" in result:
            return True

    return False


def _verify_result_message(result: str | None, last_assistant_text: str | None) -> None:
    """Log an error if ResultMessage.result diverges from the last AssistantMessage text."""
    if not result:
        return
    if last_assistant_text is None:
        logfire.error(
            "ResultMessage has content but no prior AssistantMessage text was seen - final answer may be lost",
            result_preview=result[:300],
        )
    elif result.strip() != last_assistant_text.strip():
        diff = "".join(
            difflib.unified_diff(
                last_assistant_text.splitlines(keepends=True),
                result.splitlines(keepends=True),
                fromfile="last_assistant_text",
                tofile="result",
            )
        )
        logfire.error(
            "ResultMessage.result differs from last AssistantMessage text - final answer may be lost",
            diff=diff,
        )


CLAUDE_COMPACTION_PROMPT = "Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, do not stop tasks early due to token budget concerns. Always be as persistent and autonomous as possible and complete tasks fully, even if the end of your budget is approaching. Never artificially stop any task early regardless of the context remaining."


class ClaudeCodeAgent(BaseAgent):
    """Claude Code agent that delegates behavior to a Role.

    This agent uses a Role instance to define its system prompt, tools (virtual and function),
    and context, making the agent behavior completely determined by the role configuration.
    """

    def __init__(
        self,
        role: AgentRole,
        model: LanguageModel | None,
        session_id: str | None = None,
        working_dir: str | None = None,
        additional_tools: list[Tool] | None = None,
        custom_instructions: str | None = None,
    ):
        """Initialize Claude Code agent with role.

        Args:
            role: Role defining agent behavior (prompts, tools, context)
            model: Language model instance, or None to use Claude Code's default model
            session_id: Optional session ID to resume previous conversation
            working_dir: Optional path to codebase directory
            additional_tools: Extra tools to add beyond those defined by the role
            custom_instructions: User-defined instructions to append to the base system prompt
        """
        if model is not None and model.provider != LLMProvider.ANTHROPIC:
            raise ValueError(f"Unsupported model provider for Claude Code: {model.provider}")

        super().__init__(role, model, additional_tools, custom_instructions)

        self.session_id = session_id
        self.working_dir = working_dir
        # Convert PydanticAI tools to virtual tools and function tools
        self._virtual_tools, self._function_tools = self._partition_tools()

    def _partition_tools(self) -> tuple[dict[str, VirtualTool], list[Tool] | None]:
        """Partition tools into virtual tools and function tools.

        Tools with requires_approval=True become virtual tools.
        Tools with requires_approval=False become regular Tool instances (passed to ClaudeClient).

        Returns:
            Tuple of (virtual_tools dict, function_tools list of Tool instances or None)
        """
        virtual_tools: dict[str, VirtualTool] = {}
        function_tools: list[Tool] = []

        for tool in self.get_tools():
            if tool.requires_approval:
                # Convert to virtual tool
                virtual_tool = VirtualTool(tool)
                virtual_tools[virtual_tool.tool_name] = virtual_tool
            else:
                # Add as regular Tool instance (ClaudeClient will handle it)
                function_tools.append(tool)

        return virtual_tools, function_tools if function_tools else None

    async def _create_client(self) -> ClaudeClient:
        """Create a Claude client with the current system prompt and session ID.

        This is called on each run to ensure the system prompt includes
        the latest document state.

        Returns:
            Configured ClaudeClient instance
        """
        system_prompt = await self._build_system_prompt()
        logfire.info(f"Initialising ClaudeClient in directory: {self.working_dir}")

        return ClaudeClient(
            session_id=self.session_id,
            system_prompt=system_prompt,
            tools=self._function_tools,
            allowed_builtin_tools=self.role.allowed_builtin_tools,
            model=self.model.display_full_name if self.model else None,
            cwd=self.working_dir,
            include_builtin_system_prompt=self.role.include_builtin_system_prompt,
            load_settings=self.role.include_claude_md,
        )

    async def _build_system_prompt(self) -> str:
        """Build the system prompt from role.

        Combines role description (with custom instructions), tool schemas, and state/context data.
        """
        # Get full system prompt (role prompt + custom instructions)
        role_prompt = self.get_full_system_prompt()

        # Build tool schemas from virtual tools
        virtual_tool_prompt = build_virtual_tool_schemas_section(list(self._virtual_tools.values()))

        # Get current state/context from role (async operation)
        state_context = await self.role.get_context_content()

        prompt_parts = [role_prompt, virtual_tool_prompt, state_context]

        if not self.role.include_builtin_system_prompt:
            prompt_parts.append(CLAUDE_COMPACTION_PROMPT)

        # Combine all parts
        return "\n\n".join(prompt_parts)

    def get_virtual_tool(self, tool_name: str) -> VirtualTool | None:
        """Get a virtual tool by name.

        Tools are lazily computed and cached for the lifetime of the agent instance.
        """
        return self._virtual_tools.get(tool_name)

    async def stream_events(
        self,
        prompt_or_approvals: str | ToolApprovals,
        interrupt_event: asyncio.Event | None = None,
    ) -> AsyncIterator[ConversationEvent]:
        """Stream conversation events from agent execution.

        Raises:
            ValueError: If session_id missing when processing tool approvals,
                       or if maximum retry attempts exceeded
        """
        # Check if this is tool approvals
        if isinstance(prompt_or_approvals, ToolApprovals):
            if not self.session_id:
                raise ValueError("session_id required when processing tool approvals")

            # Execute tools and format results
            result_parts: list[str] = []
            async for tool_event in self._process_tool_approvals(prompt_or_approvals):
                if isinstance(tool_event, ToolResult):
                    # Format result with outcome attribute
                    result_parts.append(tool_event.result_content)

                yield tool_event

            # Send results back to Claude wrapped in XML markers
            user_message = "\n".join(result_parts)
        else:
            user_message = prompt_or_approvals

        current_message = user_message
        # Create fresh client with current system prompt, document state, and session ID
        client = await self._create_client()

        # Track API error retry attempts separately from validation error retries
        api_error_retry_count = 0

        # Retry loop for handling virtual tool call validation errors
        for attempt in range(MAX_RETRY_ATTEMPTS + 1):
            # Capture the stream generator to ensure proper cleanup on exception
            stream_generator = client.stream(user_query=current_message, interrupt_event=interrupt_event)
            should_retry_api_error = False
            last_assistant_text: str | None = None
            try:
                # Stream messages from the client
                async for message in stream_generator:
                    if isinstance(message, ResultMessage):
                        # Check for retryable API error (check result content regardless of is_error flag)
                        if _should_retry_error_result(message.result) and api_error_retry_count < MAX_RETRY_ATTEMPTS:
                            api_error_retry_count += 1
                            # Yield SystemEvent to notify about retry
                            yield SystemEvent(
                                type=SystemEventType.API_ERROR_RETRY,
                                data={
                                    "attempt": api_error_retry_count,
                                    "max_attempts": MAX_RETRY_ATTEMPTS,
                                    "error": message.result[:200] if message.result else "Unknown error",
                                },
                                timestamp=datetime.datetime.now(datetime.UTC),
                            )
                            logfire.warning(
                                f"Retryable API error detected, retrying (attempt {api_error_retry_count}/{MAX_RETRY_ATTEMPTS})",
                                error=message.result[:200] if message.result else None,
                            )
                            # Set flag to retry with "continue" message
                            should_retry_api_error = True
                        else:
                            _verify_result_message(message.result, last_assistant_text)
                        # ResultMessage is always last - break to check retry flag or exit loop
                        break

                    if isinstance(message, SystemMessage):
                        # Set session_id from SystemMessage
                        # TODO: Instead of doing this, convert to a SystemEvent which indicates that session_id has changed, and can be handled in both ConversationService and frontend UI
                        if not self.session_id:
                            self.session_id = message.data["session_id"]
                        # Emit compaction event when conversation is being compacted
                        if message.subtype == "status" and message.data.get("status") == "compacting":
                            yield SystemEvent(
                                type=SystemEventType.COMPACTING_CONVERSATION,
                                timestamp=datetime.datetime.now(datetime.UTC),
                            )
                        continue

                    # Track raw AssistantMessage text for ResultMessage verification
                    if isinstance(message, AssistantMessage):
                        text_parts = [block.text for block in message.content if isinstance(block, TextBlock)]
                        if text_parts:
                            last_assistant_text = "\n".join(text_parts)

                    # Convert normal Message events to ConversationEvent
                    for conv_event in convert_claude_message_to_events(message, self._virtual_tools):
                        yield conv_event

                # Check if we need to retry due to API error
                if should_retry_api_error:
                    current_message = "continue"
                    continue

                # Success - exit retry loop
                break

            except InvalidVirtualToolCallError as e:
                # Explicitly close the generator to prevent context manager cleanup in wrong async context
                await stream_generator.aclose()

                # Validation failed during streaming - prepare retry message
                if attempt < MAX_RETRY_ATTEMPTS:
                    # Format error message for retry
                    current_message = format_tool_result(
                        tool_name=e.tool_name,
                        outcome=ToolCallOutcome.VALIDATION_ERROR,
                        content=e.error_message,
                    )
                    logfire.warning(
                        f"Tool call validation failed (attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}): {e}",
                        tool_name=e.tool_name,
                    )
                    # Continue to next iteration
                else:
                    # Max retries exceeded
                    raise ValueError(f"Tool call validation failed after {MAX_RETRY_ATTEMPTS} attempts: {e}") from e

    async def _process_tool_approvals(
        self,
        approvals: ToolApprovals,
    ) -> AsyncIterator[ToolCall | ToolResult]:
        """Process tool approvals and execute approved virtual tools.

        Parses the last message from session to get tool call data,
        executes approved tools, and formats results with XML markers.
        """
        if not self.session_id:
            raise ValueError("session_id required when processing tool approvals")

        session_service = ClaudeCodeSessionService()
        # Get last message from session to parse tool call
        last_message = session_service.get_last_session_message(self.session_id)
        if not last_message:
            raise ValueError(f"No messages in session {self.session_id} - cannot process tool approvals")

        # Parse virtual tool call from message text content using centralized parser
        tool_call = ClaudeResponseParser.parse_message_content(last_message.text_content)
        if not isinstance(tool_call, VirtualToolCall):
            raise ValueError("Last message does not contain a virtual tool call")

        # Should only ever actually be a single approval
        if len(approvals.approvals) != 1:
            raise ValueError("Expected exactly one tool approval")

        tool_call_id, decision = next(iter(approvals.approvals.items()))
        yield ToolCall(
            tool_call_id=tool_call_id,
            tool_name=tool_call_id,
            tool_args=tool_call.arguments,
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        # tool_call_id should match tool_name
        if tool_call_id != tool_call.tool_name:
            raise ValueError(
                f"Tool call ID mismatch: expected {tool_call.tool_name}, got {tool_call_id}. "
                f"Tool call ID must match the tool name from the session."
            )

        # Get the virtual tool
        virtual_tool = self.get_virtual_tool(tool_call.tool_name)
        if not virtual_tool:
            raise ValueError(f"Unknown virtual tool: {tool_call.tool_name}")

        if decision.approved:
            # Execute the virtual tool
            try:
                result_content = await virtual_tool.execute(tool_call.arguments)
                outcome = ToolCallOutcome.SUCCESS
            except ModelRetry as e:
                # Tool execution failed
                result_content = e.message
                outcome = ToolCallOutcome.ERROR
                logfire.warning(
                    f"Tool execution failed for {tool_call.tool_name}: {e}",
                    tool_name=tool_call.tool_name,
                )
        else:
            # Tool denied
            result_content = "Tool execution denied: " + (decision.feedback or "<No reason provided>")
            outcome = ToolCallOutcome.DENIED

        formatted_result = format_tool_result(tool_name=tool_call_id, outcome=outcome, content=result_content)

        yield ToolResult(
            tool_call_id=tool_call_id,
            result_content=formatted_result,
            is_error=(outcome != ToolCallOutcome.SUCCESS),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
