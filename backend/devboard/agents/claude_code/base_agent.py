"""Base agent class for Claude Code agents with virtual tool calling."""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from devboard.agents.claude_code.client import ClaudeClient, ClaudeCodeResult
from devboard.agents.claude_code.virtual_tools import VirtualTool, VirtualToolCall, VirtualToolRequests
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


# Response format models for Pydantic validation


class MessageResponseFormat(BaseModel):
    """Pydantic model for normal message responses."""

    type: str = Field(pattern="^message$", description="Response type must be 'message'")
    content: str = Field(description="The message content")


class ToolCallResponseFormat(BaseModel):
    """Pydantic model for tool call responses."""

    type: str = Field(pattern="^tool_call$", description="Response type must be 'tool_call'")
    tool_name: str = Field(description="Name of the tool to call")
    arguments: dict[str, Any] = Field(description="Arguments for the tool")


class BaseClaudeAgent(ABC):
    """Base class for Claude Code agents using virtual tool calling.

    This class provides the foundation for application-level agents that use
    Claude Code with a virtual tool calling pattern (JSON-structured responses).

    Subclasses should implement:
    - _build_system_prompt(): Construct the system prompt with tool schemas and context
    - _get_virtual_tools(): Return list of VirtualTool instances for this agent
    """

    def __init__(self, task: Task, document_repository: DocumentRepository):
        """Initialize the base Claude agent.

        Args:
            task: The task this agent is working on
            document_repository: Repository for document operations
        """
        self.task = task
        self.document_repo = document_repository
        self._virtual_tools: dict[str, VirtualTool] | None = None

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
        )

    @abstractmethod
    def _build_system_prompt(self) -> str:
        """Build the system prompt for this agent.

        This should include:
        - Agent role and instructions
        - Tool schemas and response format requirements
        - Current document state and context

        Returns:
            Complete system prompt string
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
        if self._virtual_tools is None:
            tools = self._get_virtual_tools()
            self._virtual_tools = {tool.tool_name: tool for tool in tools}
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

        Override to customize model selection.

        Returns:
            Model name or None to use default
        """
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
        user_message: str,
        session_id: str | None = None,
        _retry_count: int = 0,
    ) -> MessageResponse | VirtualToolRequests:
        """Run the agent with a user message.

        Args:
            user_message: The user's message/query
            session_id: Optional session ID to resume previous conversation
            _retry_count: Internal counter for retry attempts (not for external use)

        Returns:
            Either a MessageResponse (normal message) or VirtualToolRequests (tool calls)

        Raises:
            ValueError: If maximum retry attempts exceeded
        """
        # Create fresh client with current system prompt, document state, and session ID
        client = self._create_client(session_id=session_id)

        # Run the client
        result = await client.run(user_query=user_message)

        # Parse response to detect virtual tool calls with validation
        return await self._parse_response(result, _retry_count)

    async def _parse_response(
        self,
        result: ClaudeCodeResult,
        retry_count: int,
    ) -> MessageResponse | VirtualToolRequests:
        """Parse the Claude response to detect virtual tool calls with validation.

        Validates JSON format and tool arguments. If validation fails, retries
        with error feedback (up to MAX_RETRY_ATTEMPTS).

        Args:
            result: The raw ClaudeCodeResult from the client
            retry_count: Current retry attempt number

        Returns:
            Either a MessageResponse (normal message) or VirtualToolRequests

        Raises:
            ValueError: If maximum retry attempts exceeded
        """
        response_text = result.text_content.strip()

        # Try to parse as JSON
        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            # Invalid JSON format - retry if attempts remaining
            if retry_count < MAX_RETRY_ATTEMPTS:
                error_msg = (
                    f"ERROR: Your response is not valid JSON. "
                    f"JSON parsing error: {e}\n\n"
                    f"Please respond with valid JSON in one of these formats:\n"
                    f'1. Normal message: {{"type": "message", "content": "Your message"}}\n'
                    f'2. Tool call: {{"type": "tool_call", "tool_name": "...", "arguments": {{...}}}}\n\n'
                    f"Please try again with properly formatted JSON."
                )
                logger.warning(f"Invalid JSON response (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {e}")
                return await self.run(error_msg, session_id=result.session_id, _retry_count=retry_count + 1)
            else:
                # Max retries exceeded - treat as plain text message
                logger.error("Max retries exceeded for JSON parsing. Treating as plain text.")
                return MessageResponse(content=response_text, session_id=result.session_id)

        # Check if it's a dict
        if not isinstance(response_data, dict):
            if retry_count < MAX_RETRY_ATTEMPTS:
                error_msg = (
                    f"ERROR: Response must be a JSON object (dict), not {type(response_data).__name__}.\n\n"
                    f"Please respond with a JSON object in one of these formats:\n"
                    f'1. Normal message: {{"type": "message", "content": "Your message"}}\n'
                    f'2. Tool call: {{"type": "tool_call", "tool_name": "...", "arguments": {{...}}}}'
                )
                logger.warning(f"Response is not a dict (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS})")
                return await self.run(error_msg, session_id=result.session_id, _retry_count=retry_count + 1)
            else:
                return MessageResponse(content=response_text, session_id=result.session_id)

        response_type = response_data.get("type")

        # Validate response format using Pydantic models
        if response_type == "tool_call":
            return await self._handle_tool_call_response(response_data, result.session_id, retry_count)
        elif response_type == "message":
            return await self._handle_message_response(response_data, result.session_id, retry_count)
        else:
            # Unknown or missing type field
            if retry_count < MAX_RETRY_ATTEMPTS:
                error_msg = (
                    f"ERROR: Missing or invalid 'type' field in response. "
                    f"Got: {response_type!r}\n\n"
                    f"Response must include a 'type' field with value 'message' or 'tool_call'.\n"
                    f'Example: {{"type": "message", "content": "Your message"}}'
                )
                logger.warning(
                    f"Invalid response type (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {response_type}"
                )
                return await self.run(error_msg, session_id=result.session_id, _retry_count=retry_count + 1)
            else:
                return MessageResponse(content=response_text, session_id=result.session_id)

    async def _handle_message_response(
        self,
        response_data: dict,
        session_id: str,
        retry_count: int,
    ) -> MessageResponse:
        """Handle and validate a message response.

        Args:
            response_data: Raw response dict
            session_id: Session ID from the result
            retry_count: Current retry attempt number

        Returns:
            MessageResponse
        """
        try:
            # Validate using Pydantic model
            validated = MessageResponseFormat.model_validate(response_data)
            return MessageResponse(content=validated.content, session_id=session_id)

        except ValidationError as e:
            if retry_count < MAX_RETRY_ATTEMPTS:
                error_details = "\n".join([f"- {err['loc'][0]}: {err['msg']}" for err in e.errors()])
                error_msg = (
                    f"ERROR: Invalid message response format.\n\n"
                    f"Validation errors:\n{error_details}\n\n"
                    f"Expected format:\n"
                    f'{{"type": "message", "content": "Your message here"}}\n\n'
                    f"Please correct these errors and try again."
                )
                logger.warning(f"Message validation failed (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {e}")
                return await self.run(error_msg, session_id=session_id, _retry_count=retry_count + 1)
            else:
                # Fallback to raw content
                return MessageResponse(content=response_data.get("content", str(response_data)), session_id=session_id)

    async def _handle_tool_call_response(
        self,
        response_data: dict,
        session_id: str,
        retry_count: int,
    ) -> MessageResponse | VirtualToolRequests:
        """Handle and validate a tool call response.

        Args:
            response_data: Raw response dict
            session_id: Session ID from the result
            retry_count: Current retry attempt number

        Returns:
            VirtualToolRequests if valid, or MessageResponse on retry
        """
        # First validate the basic structure
        try:
            validated = ToolCallResponseFormat.model_validate(response_data)
        except ValidationError as e:
            if retry_count < MAX_RETRY_ATTEMPTS:
                error_details = "\n".join([f"- {err['loc'][0]}: {err['msg']}" for err in e.errors()])
                error_msg = (
                    f"ERROR: Invalid tool call response format.\n\n"
                    f"Validation errors:\n{error_details}\n\n"
                    f"Expected format:\n"
                    f'{{"type": "tool_call", "tool_name": "edit_task_specification", '
                    f'"arguments": {{"edits": [...], "reasoning": "..."}}}}\n\n'
                    f"Please correct these errors and try again."
                )
                logger.warning(
                    f"Tool call structure validation failed (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {e}"
                )
                return await self.run(error_msg, session_id=session_id, _retry_count=retry_count + 1)
            else:
                raise ValueError(f"Tool call validation failed after {MAX_RETRY_ATTEMPTS} attempts: {e}") from e

        # Get the virtual tool and validate arguments
        tool_name = validated.tool_name
        virtual_tool = self.get_virtual_tool(tool_name)

        if not virtual_tool:
            if retry_count < MAX_RETRY_ATTEMPTS:
                # Get available tool names for helpful error message
                available_tools = list(self._virtual_tools.keys()) if self._virtual_tools else []
                tools_list = ", ".join(available_tools) if available_tools else "none"
                error_msg = (
                    f"ERROR: Unknown tool '{tool_name}'.\n\n"
                    f"Available tools: {tools_list}\n\n"
                    f"Please use one of the available tools."
                )
                logger.warning(f"Unknown tool (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {tool_name}")
                return await self.run(error_msg, session_id=session_id, _retry_count=retry_count + 1)
            else:
                raise ValueError(f"Unknown tool '{tool_name}' after {MAX_RETRY_ATTEMPTS} attempts")

        # Validate tool arguments against the tool's schema
        try:
            # Use the tool's args_model to validate
            virtual_tool.args_model.model_validate(validated.arguments)
        except ValidationError as e:
            if retry_count < MAX_RETRY_ATTEMPTS:
                error_details = "\n".join([f"- {err['loc'][0]}: {err['msg']}" for err in e.errors()])
                error_msg = (
                    f"ERROR: Invalid arguments for tool '{tool_name}'.\n\n"
                    f"Validation errors:\n{error_details}\n\n"
                    f"Please check the tool schema and provide valid arguments."
                )
                logger.warning(
                    f"Tool arguments validation failed (attempt {retry_count + 1}/{MAX_RETRY_ATTEMPTS}): {e}"
                )
                return await self.run(error_msg, session_id=session_id, _retry_count=retry_count + 1)
            else:
                raise ValueError(
                    f"Tool arguments validation failed for '{tool_name}' after {MAX_RETRY_ATTEMPTS} attempts: {e}"
                ) from e

        # All validations passed - create VirtualToolCall
        tool_call = VirtualToolCall(tool_name=tool_name, arguments=validated.arguments)
        return VirtualToolRequests(calls=[tool_call], session_id=session_id)
