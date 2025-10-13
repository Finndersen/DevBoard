"""Base agent class for Claude Code agents with virtual tool calling."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import ValidationError

from devboard.agents.claude_code.client import ClaudeClient, ClaudeCodeResult
from devboard.agents.claude_code.message_parser import ClaudeResponseParser
from devboard.agents.claude_code.session import ClaudeCodeSessionService
from devboard.agents.claude_code.virtual_tools import (
    VirtualTool,
    VirtualToolCall,
    VirtualToolRequests,
    build_tool_schemas_section,
)
from devboard.api.schemas.agent_conversation import ToolApprovalDecision
from devboard.db.models.task import Task
from devboard.db.repositories.document import DocumentRepository

logger = logging.getLogger(__name__)

# Maximum number of retry attempts for invalid responses
MAX_RETRY_ATTEMPTS = 3


@dataclass
class MessageResponse:
    """Response from Claude Code agent containing a text message."""

    content: str
    session_id: str


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
        model_name: str,
        plan_mode: bool = False,
    ):
        """Initialize the base Claude agent.

        Args:
            task: The task this agent is working on
            document_repository: Repository for document operations
            model_name: Model ID (e.g., "anthropic:claude-sonnet-4")
            plan_mode: Whether to enable plan mode in Claude Code
        """
        self.task = task
        self.document_repo = document_repository
        self.model_name = model_name
        self._virtual_tools = {tool.tool_name: tool for tool in self._get_virtual_tools()}
        self.plan_mode = plan_mode
        self.session_service = ClaudeCodeSessionService()

    def _create_client(self, session_id: str | None = None) -> ClaudeClient:
        """Create a Claude client with the current system prompt and session ID.

        This is called on each run to ensure the system prompt includes
        the latest document state.

        Args:
            session_id: Optional session ID to resume previous conversation

        Returns:
            Configured ClaudeClient instance
        """
        system_prompt = self._build_system_prompt()

        return ClaudeClient(
            session_id=session_id,
            system_prompt=system_prompt,
            allowed_tools=self._get_allowed_tools(),
            model=self._get_model(),
            cwd=self._get_cwd(),
            plan_mode=self.plan_mode,
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
        tool_schemas = build_tool_schemas_section(list(self._virtual_tools.values()))

        # Get current state/context
        state_context = self._get_state_context()

        # Combine all parts
        return f"{role_description}\n\n{tool_schemas}\n\n{state_context}"

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

    def get_virtual_tool(self, tool_name: str) -> VirtualTool | None:
        """Get a virtual tool by name.

        Tools are lazily computed and cached for the lifetime of the agent instance.

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            VirtualTool instance or None if not found
        """
        return self._virtual_tools.get(tool_name)

    def _get_allowed_tools(self) -> list[str] | None:
        """Get list of allowed Claude Code tools for this agent.

        Override to customize tool access. By default allows common read-only tools.

        Returns:
            List of tool names or None to allow all tools
        """
        return ["Read", "Grep", "Glob", "Bash"]

    def _get_model(self) -> str | None:
        """Get the model to use for this agent.

        Strips the "anthropic:" prefix from the model name if present,
        as ClaudeClient expects just the model identifier.

        Returns:
            Model name without prefix, or None to use default
        """
        if self.model_name:
            # Remove "anthropic:" prefix if present
            return self.model_name.replace("anthropic:", "")
        return None

    def _get_cwd(self) -> str | None:
        """Get the working directory for Claude Code operations.

        Override to customize working directory.

        Returns:
            Working directory path or None to use default
        """
        return None

    async def run(
        self,
        prompt_or_approvals: str | dict[str, ToolApprovalDecision],
        session_id: str | None = None,
        _retry_count: int = 0,
    ) -> MessageResponse | VirtualToolRequests:
        """Run the agent with either a user message or tool approval results.

        Args:
            prompt_or_approvals: Either a user message string or dict of tool approval decisions
            session_id: Optional session ID to resume previous conversation
            _retry_count: Internal counter for retry attempts (not for external use)

        Returns:
            Either a MessageResponse (normal message) or VirtualToolRequests (tool calls)

        Raises:
            ValueError: If session_id missing when processing tool approvals,
                       or if maximum retry attempts exceeded
        """
        # Check if this is tool approvals
        if isinstance(prompt_or_approvals, dict):
            if not session_id:
                raise ValueError("session_id required when processing tool approvals")

            # Execute tools and format results
            results = await self._process_tool_approvals(prompt_or_approvals, session_id)

            # Send results back to Claude wrapped in XML markers
            user_message = results
        else:
            user_message = prompt_or_approvals

        # Create fresh client with current system prompt, document state, and session ID
        client = self._create_client(session_id=session_id)

        # Run the client
        result = await client.run(user_query=user_message)

        # Parse response to detect virtual tool calls with validation
        return await self._parse_response(result, _retry_count)

    async def _process_tool_approvals(
        self,
        approvals: dict[str, ToolApprovalDecision],
        session_id: str,
    ) -> str:
        """Process tool approvals and execute approved virtual tools.

        Parses the last message from session to get tool call data,
        executes approved tools, and formats results with XML markers.

        Args:
            approvals: Map of tool_name (as tool_call_id) to approval decision
            session_id: Claude Code session ID to retrieve tool call from

        Returns:
            Formatted result message with XML markers for sending back to Claude

        Raises:
            ValueError: If session has no messages or last message isn't a tool call
        """
        # Get last message from session to parse tool call
        last_message = self.session_service.get_last_session_message(session_id)
        if not last_message:
            raise ValueError("No messages in session - cannot process tool approvals")

        # Parse virtual tool call from message text content using centralized parser
        parsed = ClaudeResponseParser.parse_message(last_message.text_content)
        if not isinstance(parsed, VirtualToolCall):
            raise ValueError("Last message does not contain a virtual tool call")
        tool_call = parsed

        # Execute approved tools and build result messages
        result_parts: list[str] = []

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
                # Use modified args if provided, otherwise use args from session
                args = decision.modified_args if decision.modified_args else tool_call.arguments

                result = await virtual_tool.execute(args)
                result_text = f"✓ {tool_call.tool_name}: {result}"

            else:
                # Tool denied
                feedback = decision.feedback or "Tool execution was denied"
                result_text = f"✗ {tool_call.tool_name} DENIED: {feedback}"

            # Wrap result in XML marker
            result_parts.append(
                f'<tool_call_result tool_name="{tool_call.tool_name}">\n{result_text}\n</tool_call_result>'
            )

        # Return combined results
        return "\n\n".join(result_parts)

    def _wrap_validation_error(self, error_message: str) -> str:
        """Wrap a validation error message in XML markers.

        Args:
            error_message: The error message to wrap

        Returns:
            Error message wrapped in <validation_error> tags
        """
        return f"<validation_error>\n{error_message}\n</validation_error>"

    async def _parse_response(
        self,
        result: ClaudeCodeResult,
        retry_count: int,
    ) -> MessageResponse | VirtualToolRequests:
        """Parse the Claude response to detect virtual tool calls.

        Uses the centralized parser to consistently handle both regular messages
        and tool calls.

        Args:
            result: The raw ClaudeCodeResult from the client
            retry_count: Current retry attempt number

        Returns:
            Either a MessageResponse (normal message) or VirtualToolRequests
        """
        response_text = result.text_content.strip()

        # Use unified parser to handle both messages and tool calls
        try:
            parsed = ClaudeResponseParser.parse_message(response_text)
        except ValidationError as e:
            # Invalid tool call structure - provide feedback and retry
            if retry_count < MAX_RETRY_ATTEMPTS:
                error_details = "\n".join([f"- {err['loc'][0]}: {err['msg']}" for err in e.errors()])
                error_msg = self._wrap_validation_error(
                    f"ERROR: Invalid tool call response format.\n\n"
                    f"Validation errors:\n{error_details}\n\n"
                    f"Expected format:\n"
                    f'{{"tool_name": "edit_task_specification", '
                    f'"arguments": {{"edits": [...], "reasoning": "..."}}}}\n\n'
                    f"Please correct these errors and try again."
                )
                logger.warning(
                    f"Tool call structure validation failed (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {e}"
                )
                return await self.run(
                    prompt_or_approvals=error_msg, session_id=result.session_id, _retry_count=retry_count + 1
                )
            else:
                raise ValueError(f"Tool call validation failed after {MAX_RETRY_ATTEMPTS} attempts: {e}") from e

        if isinstance(parsed, VirtualToolCall):
            # Tool call detected - validate and handle it
            return await self._handle_virtual_tool_call_response(parsed, result.session_id, retry_count)
        else:
            # Normal message
            return MessageResponse(content=parsed, session_id=result.session_id)

    async def _handle_virtual_tool_call_response(
        self,
        tool_call: VirtualToolCall,
        session_id: str,
        retry_count: int,
    ) -> MessageResponse | VirtualToolRequests:
        """Handle and validate a tool call response.

        Args:
            tool_call: Parsed and structurally validated VirtualToolCall
            session_id: Session ID from the result
            retry_count: Current retry attempt number

        Returns:
            VirtualToolRequests if valid, or MessageResponse on retry
        """
        # Get the virtual tool and validate arguments
        tool_name = tool_call.tool_name
        virtual_tool = self.get_virtual_tool(tool_name)

        if not virtual_tool:
            if retry_count < MAX_RETRY_ATTEMPTS:
                # Get available tool names for helpful error message
                available_tools = list(self._virtual_tools.keys()) if self._virtual_tools else []
                tools_list = ", ".join(available_tools) if available_tools else "none"
                error_msg = self._wrap_validation_error(
                    f"ERROR: Unknown tool '{tool_name}'.\n\n"
                    f"Available tools: {tools_list}\n\n"
                    f"Please use one of the available tools."
                )
                logger.warning(f"Unknown tool (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {tool_name}")
                return await self.run(
                    prompt_or_approvals=error_msg, session_id=session_id, _retry_count=retry_count + 1
                )
            else:
                raise ValueError(f"Unknown tool '{tool_name}' after {MAX_RETRY_ATTEMPTS} attempts")

        # Validate tool arguments against the tool's schema
        try:
            # Use the tool's args_model to validate
            virtual_tool.args_model.model_validate(tool_call.arguments)
        except ValidationError as e:
            if retry_count < MAX_RETRY_ATTEMPTS:
                error_details = "\n".join([f"- {err['loc'][0]}: {err['msg']}" for err in e.errors()])
                error_msg = self._wrap_validation_error(
                    f"ERROR: Invalid arguments for tool '{tool_name}'.\n\n"
                    f"Validation errors:\n{error_details}\n\n"
                    f"Please check the tool schema and provide valid arguments."
                )
                logger.warning(
                    f"Tool arguments validation failed (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {e}"
                )
                return await self.run(
                    prompt_or_approvals=error_msg, session_id=session_id, _retry_count=retry_count + 1
                )
            else:
                raise ValueError(
                    f"Tool arguments validation failed for '{tool_name}' after {MAX_RETRY_ATTEMPTS} attempts: {e}"
                ) from e

        # All validations passed - return the tool call
        return VirtualToolRequests(calls=[tool_call], session_id=session_id)
