"""Base agent class for Claude Code agents with virtual tool calling."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import logfire
from claude_agent_sdk import Message, ResultMessage
from pydantic import ValidationError

from devboard.agents.engines.claude_code.client import ClaudeClient, ClaudeCodeToolFunc
from devboard.agents.engines.claude_code.message_parser import (
    ClaudeResponseParser,
    TextResponse,
    ToolCallOutcome,
    VirtualToolCall,
    VirtualToolRequests,
)
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionService
from devboard.agents.engines.claude_code.virtual_tools import (
    ToolCallError,
    VirtualTool,
    build_virtual_tool_schemas_section,
)
from devboard.agents.language_models import LanguageModel, LLMProvider
from devboard.agents.prompts import DOCUMENT_EDIT_PROMPT
from devboard.api.schemas.agent_conversation import ToolApprovalDecision
from devboard.db.models.task import Task
from devboard.db.repositories.document import DocumentRepository

# Maximum number of retry attempts for invalid responses
MAX_RETRY_ATTEMPTS = 3

FinalResult = TextResponse | VirtualToolRequests


class ClaudeCodeAgent(ABC):
    """Base class for Claude Code agents using virtual tool calling.

    This class provides the foundation for application-level agents that use
    Claude Code with a virtual tool calling pattern (JSON-structured responses).

    Subclasses should implement:
    - _build_system_prompt(): Construct the system prompt with tool schemas and context
    - _get_virtual_tools(): Return list of VirtualTool instances for this agent
    """

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        model: LanguageModel,
        session_id: str | None = None,
        include_builtin_system_prompt: bool = False,
        include_claude_md: bool = False,
    ):
        """Initialize the base Claude agent.

        Args:
            task: The task this agent is working on
            document_repository: Repository for document operations
            model: Language model instance
            session_id: Optional session ID to resume previous conversation
            include_builtin_system_prompt: Whether to include Claude's built-in system prompt
            include_claude_md: Whether to include CLAUDE.md file in system prompt
        """
        if not model.provider == LLMProvider.ANTHROPIC:
            raise ValueError(f"Unsupported model provider for Claude Code: {model.provider}")

        self.task = task
        self.document_repo = document_repository
        self.model = model
        self.session_id = session_id
        self._virtual_tools = {tool.tool_name: tool for tool in self._get_virtual_tools()}
        self.session_service = ClaudeCodeSessionService()
        self.include_builtin_system_prompt = include_builtin_system_prompt
        self.include_claude_md = include_claude_md

    def _create_client(self) -> ClaudeClient:
        """Create a Claude client with the current system prompt and session ID.

        This is called on each run to ensure the system prompt includes
        the latest document state.

        Returns:
            Configured ClaudeClient instance
        """
        system_prompt = self._build_system_prompt()

        # Use codebase directory if available
        cwd = self.task.codebase.local_path if self.task.codebase else None

        return ClaudeClient(
            session_id=self.session_id,
            system_prompt=system_prompt,
            tools=self._get_function_tools(),
            allowed_builtin_tools=self._get_allowed_builtin_tools(),
            model=self.model.display_full_name,
            cwd=cwd,
            include_builtin_system_prompt=self.include_builtin_system_prompt,
            include_claude_md=self.include_claude_md,
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt for this agent.

        Combines role description, tool schemas, and state/context data.
        Subclasses should implement _get_role_description() and _get_state_context().

        Returns:
            Complete system prompt string
        """
        # Get components from subclass
        role_description = self._get_role_description()

        # Build tool schemas from virtual tools
        tool_schemas = build_virtual_tool_schemas_section(list(self._virtual_tools.values()))

        # Get current state/context
        state_context = self._get_state_context()

        # Combine all parts
        return "\n\n".join([role_description, DOCUMENT_EDIT_PROMPT, tool_schemas, state_context])

    @abstractmethod
    def _get_role_description(self) -> str:
        """Get the agent role description and behavioral guidelines.

        This should describe:
        - The agent's purpose and role
        - Guidelines for behavior and interaction
        - Any specific rules or constraints

        Returns:
            Role description string
        """
        pass

    @abstractmethod
    def _get_state_context(self) -> str:
        """Get the current state and context information for the agent.

        This should provide:
        - Current task information (name, status, etc.)
        - Document states (which documents and their content)
        - Any other relevant context

        Returns:
            State/context string
        """
        pass

    @abstractmethod
    def _get_virtual_tools(self) -> list[VirtualTool]:
        """Get the list of virtual tools for this agent.

        This should return initialized VirtualTool instances that will be
        used to build the system prompt and execute approved tool calls.

        Returns:
            List of VirtualTool instances
        """
        pass

    def _get_function_tools(self) -> list[ClaudeCodeToolFunc] | None:
        """Get the list of regular function tools for this agent.

        These are tools that don't require approval and will be passed to
        ClaudeClient as normal tools (not virtual tools requiring JSON responses).

        Override this method to provide regular tools. By default returns None.

        Returns:
            List of sync or async functions that return strings, or None
        """
        return None

    def get_virtual_tool(self, tool_name: str) -> VirtualTool | None:
        """Get a virtual tool by name.

        Tools are lazily computed and cached for the lifetime of the agent instance.

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            VirtualTool instance or None if not found
        """
        return self._virtual_tools.get(tool_name)

    def _get_allowed_builtin_tools(self) -> list[str] | None:
        """Get list of allowed Claude Code tools for this agent.

        Override to customize tool access. By default allows common read-only tools.

        Returns:
            List of tool names or None to allow all tools
        """
        return ["Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch"]

    async def stream_events(
        self,
        prompt_or_approvals: str | dict[str, ToolApprovalDecision],
        _retry_count: int = 0,
    ) -> AsyncIterator[Message | FinalResult]:
        """Stream messages from Claude Code execution and parse final result.

        Args:
            prompt_or_approvals: Either a user message string or dict of tool approval decisions
            _retry_count: Internal counter for retry attempts (not for external use)

        Yields:
            Message objects from Claude SDK, and final MessageResponse or VirtualToolRequests

        Raises:
            ValueError: If session_id missing when processing tool approvals
        """
        # Check if this is tool approvals
        if isinstance(prompt_or_approvals, dict):
            if not self.session_id:
                raise ValueError("session_id required when processing tool approvals")

            # Execute tools and format results
            results = await self._process_tool_approvals(prompt_or_approvals)

            # Send results back to Claude wrapped in XML markers
            user_message = results
        else:
            user_message = prompt_or_approvals

        # Create fresh client with current system prompt, document state, and session ID
        client = self._create_client()

        # Stream messages from the client
        result_message = None
        async for message in client.stream(user_query=user_message):
            # Capture the ResultMessage for parsing
            if isinstance(message, ResultMessage):
                result_message = message
            else:
                yield message

        # Parse the final result
        if not result_message:
            raise RuntimeError("No ResultMessage received from Claude SDK")

        # Update session_id from result if not already set
        if not self.session_id:
            self.session_id = result_message.session_id

        parsed_result = await self._parse_response(result_message, _retry_count)
        yield parsed_result

    async def run(
        self,
        prompt_or_approvals: str | dict[str, ToolApprovalDecision],
        _retry_count: int = 0,
    ) -> FinalResult:
        """Run the agent with either a user message or tool approval results.

        Args:
            prompt_or_approvals: Either a user message string or dict of tool approval decisions
            _retry_count: Internal counter for retry attempts (not for external use)

        Returns:
            Either a MessageResponse (normal message) or VirtualToolRequests (tool calls)

        Raises:
            ValueError: If session_id missing when processing tool approvals,
                       or if maximum retry attempts exceeded
        """
        # Use stream_events and get the final parsed result
        final_result = None

        async for event in self.stream_events(prompt_or_approvals, _retry_count):
            # The last event will be the parsed MessageResponse or VirtualToolRequests
            if isinstance(event, FinalResult):
                final_result = event

        if final_result is None:
            raise RuntimeError("No final result received from stream_events")

        return final_result

    async def _process_tool_approvals(
        self,
        approvals: dict[str, ToolApprovalDecision],
    ) -> str:
        """Process tool approvals and execute approved virtual tools.

        Parses the last message from session to get tool call data,
        executes approved tools, and formats results with XML markers.

        Args:
            approvals: Map of tool_name (as tool_call_id) to approval decision

        Returns:
            Formatted result message with XML markers for sending back to Claude

        Raises:
            ValueError: If session has no messages or last message isn't a tool call
        """
        if not self.session_id:
            raise ValueError("session_id required when processing tool approvals")

        # Get last message from session to parse tool call
        last_message = self.session_service.get_last_session_message(self.session_id)
        if not last_message:
            raise ValueError("No messages in session - cannot process tool approvals")

        # Parse virtual tool call from message text content using centralized parser
        tool_call = ClaudeResponseParser.parse_message(last_message.text_content)
        if not isinstance(tool_call, VirtualToolCall):
            raise ValueError("Last message does not contain a virtual tool call")

        result_parts: list[str] = []

        # Should only ever actually be a single approval
        for tool_call_id, decision in approvals.items():
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
                except ToolCallError as e:
                    # Tool execution failed
                    result_content = str(e)
                    outcome = ToolCallOutcome.ERROR
                    logfire.warning(
                        f"Tool execution failed for {tool_call.tool_name}: {e}",
                        tool_name=tool_call.tool_name,
                    )
            else:
                # Tool denied
                result_content = "Tool execution denied: " + (decision.feedback or "<No reason provided>")
                outcome = ToolCallOutcome.DENIED

            # Format result with outcome attribute
            result_parts.append(
                self._format_tool_result(tool_name=tool_call.tool_name, outcome=outcome, content=result_content)
            )

        # Return combined results
        return "\n\n".join(result_parts)

    def _format_tool_result(self, tool_name: str, outcome: ToolCallOutcome, content: str) -> str:
        """Format a tool result message with XML markers.

        Args:
            tool_name: Name of the tool
            outcome: Outcome of the tool call enum value
            content: Result content or error message

        Returns:
            Formatted tool result message with XML markers
        """
        # Get string value from enum
        outcome_str = outcome.value if isinstance(outcome, ToolCallOutcome) else outcome
        return f'<tool_call_result tool_name="{tool_name}" outcome="{outcome_str}">\n{content}\n</tool_call_result>'

    async def _retry_on_validation_error(
        self,
        error_message: str,
        tool_name: str,
        retry_count: int,
        error_description: str,
    ) -> FinalResult:
        """Handle retry logic for validation errors.

        Args:
            error_message: The validation error message to send to the agent
            tool_name: Tool name for XML marker and error messages
            retry_count: Current retry count
            error_description: Description of the error for logging and exception

        Returns:
            Result from retry attempt

        Raises:
            ValueError: If max retry attempts exceeded
        """
        if retry_count < MAX_RETRY_ATTEMPTS:
            # Use validation_error outcome for the tool result
            formatted_error = self._format_tool_result(
                tool_name=tool_name, outcome=ToolCallOutcome.VALIDATION_ERROR, content=error_message
            )
            logfire.warning(f"{error_description} (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS})")
            return await self.run(prompt_or_approvals=formatted_error, _retry_count=retry_count + 1)
        else:
            raise ValueError(f"{error_description} after {MAX_RETRY_ATTEMPTS} attempts")

    async def _parse_response(
        self,
        result_message: ResultMessage,
        retry_count: int,
    ) -> FinalResult:
        """Parse the Claude response to detect virtual tool calls.

        Uses the centralized parser to consistently handle both regular messages
        and tool calls.

        Args:
            result_message: The ResultMessage from Claude SDK
            retry_count: Current retry attempt number

        Returns:
            Either a MessageResponse (normal message) or VirtualToolRequests
        """
        if not result_message.result:
            raise RuntimeError("ResultMessage has no result content")

        response_text = result_message.result.strip()

        # Use unified parser to handle both messages and tool calls
        parsed = ClaudeResponseParser.parse_message(response_text)

        # Handle each message type
        if isinstance(parsed, VirtualToolCall):
            # Tool call is valid - validate arguments and handle it
            return await self._validate_virtual_tool_call_response(parsed, retry_count)
        elif isinstance(parsed, TextResponse):
            # Normal message
            return parsed
        else:
            raise ValueError(f"Expected VirtualToolCall or TextMessage from agent response, got {type(parsed)}")

    async def _validate_virtual_tool_call_response(
        self,
        tool_call: VirtualToolCall,
        retry_count: int,
    ) -> FinalResult:
        """
        Validate a tool call response, making a retry request if there are any validation errors.
        In this case, the model may respond with a standard message response instead of another tool call attempt.
        These intermediate retry messages will not be streamed back to the caller.

        Args:
            tool_call: Parsed and structurally validated VirtualToolCall
            retry_count: Current retry attempt number

        Returns:
            VirtualToolRequests if valid, or MessageResponse on retry
        """
        # Check if tool call is structurally valid
        if not tool_call.valid:
            # Invalid tool call structure - provide feedback and retry
            error_msg = (
                f"ERROR: {tool_call.validation_error}\n\n"
                f"Expected format:\n"
                f'{{"tool_name": "<tool_name>", '
                f'"arguments": {{"arg1": [...], "arg2": "..."}}}}\n\n'
                f"Please correct these errors and try again."
            )
            return await self._retry_on_validation_error(
                error_message=error_msg,
                tool_name=tool_call.tool_name,
                retry_count=retry_count,
                error_description=f"Tool call validation failed: {tool_call.validation_error}",
            )

        # Get the virtual tool and validate arguments
        tool_name = tool_call.tool_name
        virtual_tool = self.get_virtual_tool(tool_name)

        if not virtual_tool:
            # Get available tool names for helpful error message
            available_tools = list(self._virtual_tools.keys()) if self._virtual_tools else []
            tools_list = ", ".join(available_tools) if available_tools else "none"
            error_msg = (
                f"ERROR: Unknown tool '{tool_name}'.\n\n"
                f"Available tools: {tools_list}\n\n"
                f"Please use one of the available tools."
            )
            return await self._retry_on_validation_error(
                error_message=error_msg,
                tool_name=tool_name,
                retry_count=retry_count,
                error_description=f"Unknown tool '{tool_name}'",
            )

        # Validate tool arguments against the tool's schema
        try:
            # Use the tool's args_model to validate
            virtual_tool.args_model.model_validate(tool_call.arguments)
        except ValidationError as e:
            error_details = "\n".join([f"- {err['loc'][0]}: {err['msg']}" for err in e.errors()])
            error_msg = (
                f"ERROR: Invalid arguments for tool '{tool_name}'.\n\n"
                f"Validation errors:\n{error_details}\n\n"
                f"Please check the tool schema and provide valid arguments."
            )
            return await self._retry_on_validation_error(
                error_message=error_msg,
                tool_name=tool_name,
                retry_count=retry_count,
                error_description=f"Tool arguments validation failed for '{tool_name}': {e}",
            )

        # All validations passed - return the tool call
        return VirtualToolRequests(calls=[tool_call])
