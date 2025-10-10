"""Claude Code agent conversation service with virtual tool calling."""

import logging
from datetime import datetime

import logfire

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.claude_code.base_agent import BaseClaudeAgent
from devboard.agents.claude_code.session import ClaudeCodeSessionService
from devboard.agents.claude_code.virtual_tools import (
    VirtualToolCall,
    VirtualToolRequests,
)
from devboard.api.schemas.agent_conversation import (
    ConversationMessage,
    MessageRole,
    PromptResponse,
    PromptResponseType,
    ToolApprovalDecision,
    ToolCallRequest,
)
from devboard.db.models import Conversation
from devboard.db.repositories.conversation import ConversationRepository

logger = logging.getLogger(__name__)


class ClaudeCodeConversationService(BaseAgentConversationService):
    """Service for Claude Code agent conversations with virtual tool calling.

    This service manages:
    - Claude Code session continuity via external_session_id
    - Virtual tool call parsing and execution (from session history)
    - Tool approval workflow

    Note: Claude Code manages its own session files. This service does NOT
    store messages in the database - it reads from session files as needed.
    """

    def __init__(
        self,
        conversation: Conversation,
        agent: BaseClaudeAgent,
        conversation_repository: ConversationRepository,
    ):
        """Initialize Claude Code conversation service.

        Args:
            conversation: Conversation instance with session tracking
            agent: Claude Code agent (TaskSpecificationAgent, TaskPlanningAgent, etc.)
            conversation_repository: Repository for conversation operations (saving session ID)
        """
        self.conversation = conversation
        self.agent = agent
        self.conversation_repo = conversation_repository
        self.session_service = ClaudeCodeSessionService()

    @property
    def session_id(self) -> str | None:
        """Get the current Claude session ID from the conversation."""
        return self.conversation.external_session_id

    def _save_session_id(self, session_id: str):
        """Save the Claude session ID to the conversation and persist to database."""
        self.conversation_repo.update_external_session_id(self.conversation.id, session_id)
        # Also update the local instance for consistency
        self.conversation.external_session_id = session_id

    async def send_message(self, message: str) -> PromptResponse:
        """Send a message to the Claude Code agent and get a response.

        Messages are stored in Claude Code session files, not in the database.

        Args:
            message: The user's message

        Returns:
            PromptResponse containing either a message or tool approval requests
        """
        with logfire.span(
            "claude_code_conversation.send_message",
            conversation_id=self.conversation.id,
            message_length=len(message),
        ):
            # Run the agent with current session_id
            # Agent stores messages in Claude Code session files
            result = await self.agent.run(user_message=message, session_id=self.session_id)

            # Update session_id if it changed (e.g., first run creates new session)
            if result.session_id != self.session_id:
                self._save_session_id(result.session_id)

            if isinstance(result, VirtualToolRequests):
                # Convert to API schema format
                # Use tool_name as tool_call_id (only one tool call allowed at a time)
                tool_requests = [
                    ToolCallRequest(
                        tool_call_id=call.tool_name,  # Use tool_name as ID
                        tool_name=call.tool_name,
                        tool_args=call.arguments,
                    )
                    for call in result.calls
                ]

                return PromptResponse(
                    type=PromptResponseType.TOOL_REQUEST,
                    message=None,
                    tool_requests=tool_requests,
                )

            else:
                # Normal text response (MessageResponse)
                message = ConversationMessage(
                    id=0,
                    role=MessageRole.AGENT,
                    text_content=result.content,
                    timestamp=datetime.now(),
                )

                return PromptResponse(
                    type=PromptResponseType.MESSAGE,
                    message=message,
                    tool_requests=None,
                )

    async def process_tool_approvals(self, approvals: dict[str, ToolApprovalDecision]) -> PromptResponse:
        """Process user's tool approval decisions and execute approved tools.

        Parses tool call data from Claude Code session history, executes approved tools,
        and sends results back to Claude to continue the conversation.

        Args:
            approvals: Map of tool_name (as tool_call_id) to approval decision

        Returns:
            PromptResponse with next agent message or additional tool requests
        """
        with logfire.span(
            "claude_code_conversation.process_tool_approvals",
            conversation_id=self.conversation.id,
            approval_count=len(approvals),
        ):
            # Get last message from session to parse tool call
            if not self.session_id:
                raise ValueError("No session ID available - cannot process tool approvals")

            last_message = self.session_service.get_last_session_message(self.session_id)
            if not last_message:
                raise ValueError("No messages in session - cannot process tool approvals")

            # Parse virtual tool call from message text content
            tool_call = self._parse_tool_call_from_text(last_message.text_content)
            if not tool_call:
                raise ValueError("Last message does not contain a virtual tool call")

            # Execute approved tools and build result message
            result_parts: list[str] = []

            for tool_call_id, decision in approvals.items():
                # tool_call_id should match tool_name
                if tool_call_id != tool_call.tool_name:
                    raise ValueError(
                        f"Tool call ID mismatch: expected {tool_call.tool_name}, got {tool_call_id}. "
                        f"Tool call ID must match the tool name from the session."
                    )

                # Get the virtual tool from agent
                virtual_tool = self.agent.get_virtual_tool(tool_call.tool_name)
                if not virtual_tool:
                    raise ValueError(f"Unknown virtual tool: {tool_call.tool_name}")

                if decision.approved:
                    # Execute the virtual tool
                    # Use modified args if provided, otherwise use args from session
                    args = decision.modified_args if decision.modified_args else tool_call.arguments

                    result = await virtual_tool.execute(args)
                    result_parts.append(f"✓ {tool_call.tool_name}: {result}")

                else:
                    # Tool denied
                    feedback = decision.feedback or "Tool execution was denied"
                    result_parts.append(f"✗ {tool_call.tool_name} DENIED: {feedback}")

            # Continue conversation with results
            results_message = "\n".join(result_parts)

            # Send results back to Claude to continue
            # Results will be stored in Claude Code session files
            return await self.send_message(results_message)

    def _parse_tool_call_from_text(self, text: str) -> VirtualToolCall | None:
        """Parse a virtual tool call from message text content.

        Args:
            text: The text content from an assistant message

        Returns:
            VirtualToolCall if text contains a valid tool call, None otherwise
        """
        import json

        # Try to parse JSON from text
        try:
            data = json.loads(text.strip())

            # Check if it's a tool call
            if data.get("type") == "tool_call":
                # Parse using Pydantic model for validation
                return VirtualToolCall.model_validate(data)

        except (json.JSONDecodeError, ValueError):
            # Not valid JSON or not a valid tool call
            pass

        return None
