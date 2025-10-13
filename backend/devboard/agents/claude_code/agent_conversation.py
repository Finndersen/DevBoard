"""Claude Code agent conversation service with virtual tool calling."""

import logging
from datetime import datetime

import logfire

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.claude_code.base_agent import ClaudeCodeAgent
from devboard.agents.claude_code.message_parser import ClaudeMessageType, ClaudeResponseParser
from devboard.agents.claude_code.session import ClaudeCodeSessionService, SessionMessage, SessionMessageRole
from devboard.agents.claude_code.virtual_tools import VirtualToolRequests
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
        agent: ClaudeCodeAgent,
        conversation_repository: ConversationRepository,
    ):
        """Initialize Claude Code conversation service.

        Args:
            conversation: Conversation instance with session tracking
            agent: Claude Code agent (TaskSpecificationAgent, TaskPlanningAgent, etc.)
            conversation_repository: Repository for conversation operations (saving session ID)
        """
        super().__init__(conversation, conversation_repository)
        self.agent = agent

    @property
    def session_id(self) -> str | None:
        """Get the current Claude session ID from the conversation."""
        return self.conversation.external_session_id

    async def _run_agent_and_convert_response(
        self,
        prompt_or_approvals: str | dict[str, ToolApprovalDecision],
    ) -> PromptResponse:
        """Run the agent and convert the result to a PromptResponse.

        This method handles:
        - Running the agent with current session_id
        - Updating session_id if it changed
        - Converting result to PromptResponse (either message or tool requests)

        Args:
            prompt_or_approvals: Either a user message or tool approval decisions

        Returns:
            PromptResponse containing either a message or tool approval requests
        """
        # Run the agent with current session_id
        result = await self.agent.run(prompt_or_approvals=prompt_or_approvals, session_id=self.session_id)

        # Update session_id if it changed (e.g., first run creates new session)
        if result.session_id != self.session_id:
            self.conversation_repo.update_external_session_id(self.conversation, result.session_id)

        # Convert result to PromptResponse
        if isinstance(result, VirtualToolRequests):
            # Convert to tool request format
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
                role=MessageRole.AGENT,
                text_content=result.content,
                timestamp=datetime.now(),
            )

            return PromptResponse(
                type=PromptResponseType.MESSAGE,
                message=message,
                tool_requests=None,
            )

    async def send_message(self, message: str) -> PromptResponse:
        """Send a message to the Claude Code agent and get a response.

        Messages are stored in Claude Code session files, not in the database.

        Args:
            message: The user's message

        Returns:
            PromptResponse containing either a message or tool approval requests
        """
        return await self._run_agent_and_convert_response(message)

    async def process_tool_approvals(self, approvals: dict[str, ToolApprovalDecision]) -> PromptResponse:
        """Process user's tool approval decisions and execute approved tools.

        Delegates tool execution to the agent, which parses tool calls from session history,
        executes approved tools, and returns the next response.

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
            if not self.session_id:
                raise ValueError("No session ID available - cannot process tool approvals")

            return await self._run_agent_and_convert_response(approvals)

    async def get_conversation_messages(self) -> list[ConversationMessage]:
        """Retrieve all messages for the Claude Code conversation.

        Messages are loaded from Claude Code session files, not from the database.
        Claude Code manages its own session storage in ~/.claude/projects.

        Returns:
            List of ConversationMessage instances in chronological order.
            Returns empty list if no session_id (conversation hasn't started or was cleared).
        """
        # Return empty list if no session exists yet
        if not self.session_id:
            return []

        # Load low-level session messages
        claude_session_service = ClaudeCodeSessionService()
        session_messages = claude_session_service.load_session_messages(self.session_id)

        # Convert to ConversationMessage with filtering
        conversation_messages: list[ConversationMessage] = []
        for session_msg in session_messages:
            conv_msg = self._session_message_to_conversation(session_msg)
            if conv_msg:
                conversation_messages.append(conv_msg)

        return conversation_messages

    def _session_message_to_conversation(self, session_msg: SessionMessage) -> ConversationMessage | None:
        """Convert a SessionMessage to a ConversationMessage with filtering.

        Filters out:
        - Messages with <validation_error> tags (validation errors from agent)
        - Messages with <tool_call_result> tags (tool execution results)
        - Tool result messages (user messages with tool_result blocks)
        - Assistant messages with only tool calls (no text content)

        Args:
            session_msg: SessionMessage to convert

        Returns:
            ConversationMessage if message should be included, None if filtered out
        """
        # Skip tool result messages
        if session_msg.tool_results:
            return None

        # Get text content using the property
        text_content = session_msg.text_content

        # Skip if no text content (only tool calls for assistant messages)
        if not text_content:
            return None

        # Only include standard text messages (Not virtual tool calls or validation errors etc)
        message_type = ClaudeResponseParser.detect_message_type(text_content)
        if message_type != ClaudeMessageType.MESSAGE:
            return None

        # Determine role for ConversationMessage
        conv_role = MessageRole.USER if session_msg.role == SessionMessageRole.USER else MessageRole.AGENT

        return ConversationMessage(
            role=conv_role,
            text_content=text_content,
            timestamp=session_msg.timestamp,
        )
