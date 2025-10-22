"""Claude Code agent conversation service with virtual tool calling."""

import datetime

import logfire
from claude_agent_sdk import AssistantMessage, ToolResultBlock, ToolUseBlock, UserMessage

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines.claude_code.agent import ClaudeCodeAgent
from devboard.agents.engines.claude_code.message_parser import (
    ClaudeResponseParser,
    TextResponse,
    VirtualToolCall,
    VirtualToolRequests,
    VirtualToolResult,
)
from devboard.agents.engines.claude_code.session import (
    ClaudeCodeSessionService,
    SessionMessage,
    SessionMessageRole,
)
from devboard.agents.language_models import llm_registry
from devboard.agents.roles.base import Role
from devboard.api.schemas.agent_conversation import (
    ConversationEvent,
    ConversationMessage,
    MessageRole,
    ToolApprovalDecision,
    ToolCall,
    ToolCallRequest,
    ToolResult,
)
from devboard.db.models import Conversation
from devboard.db.repositories.conversation import ConversationRepository


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
        role: Role,
        conversation_repository: ConversationRepository,
        codebase_path: str | None = None,
    ):
        """Initialize Claude Code conversation service.

        Args:
            conversation: Conversation instance with session tracking
            role: The Role defining agent behavior
            conversation_repository: Repository for conversation operations (saving session ID)
            codebase_path: Optional path to codebase directory
        """
        super().__init__(conversation, conversation_repository)
        self.role = role
        self.codebase_path = codebase_path

    @property
    def session_id(self) -> str | None:
        """Get the current Claude session ID from the conversation."""
        return self.conversation.external_session_id

    async def send_message(self, message: str) -> list[ConversationEvent]:
        """Send a message to the Claude Code agent and get a response.

        Messages are stored in Claude Code session files, not in the database.

        Args:
            message: The user's message

        Returns:
            List of ConversationEvent instances representing all new events generated
            during message processing (including tool calls, results, and final message)
        """
        return await self._handle_agent_execution(prompt_or_approvals=message)

    async def process_tool_approvals(self, approvals: dict[str, ToolApprovalDecision]) -> list[ConversationEvent]:
        """Process user's tool approval decisions and execute approved tools.

        Delegates tool execution to the agent, which parses tool calls from session history,
        executes approved tools, and returns the next response.

        Args:
            approvals: Map of tool_name (as tool_call_id) to approval decision

        Returns:
            List of ConversationEvent instances representing all new events generated
            during approval processing (including tool results and final message)
        """
        with logfire.span(
            "claude_code_conversation.process_tool_approvals",
            conversation_id=self.conversation.id,
            approval_count=len(approvals),
        ):
            if not self.session_id:
                raise ValueError("No session ID available - cannot process tool approvals")

            return await self._handle_agent_execution(prompt_or_approvals=approvals)

    def _get_agent(self) -> ClaudeCodeAgent:
        """Create and return an agent instance.

        This method can be patched in tests to return a mock agent.

        Returns:
            ClaudeCodeAgent instance configured with role, model, and session
        """
        model = llm_registry.get(self.conversation.model_id) if self.conversation.model_id else None
        return ClaudeCodeAgent(
            role=self.role,
            model=model,
            session_id=self.conversation.external_session_id,
            codebase_path=self.codebase_path,
        )

    async def _handle_agent_execution(
        self, prompt_or_approvals: str | dict[str, ToolApprovalDecision]
    ) -> list[ConversationEvent]:
        """Handle agent execution using streaming and convert to events.

        This is the shared implementation for both send_message() and process_tool_approvals().

        Args:
            prompt_or_approvals: Either a user message or tool approval decisions

        Returns:
            List of conversation events generated during execution
        """
        events: list[ConversationEvent] = []

        agent = self._get_agent()

        # Stream events from agent
        async for event in agent.stream_events(prompt_or_approvals=prompt_or_approvals):
            timestamp = datetime.datetime.now(datetime.UTC)
            # Convert stream events to conversation events
            # Extract tool calls from AssistantMessage if present
            if isinstance(event, AssistantMessage):
                for content_block in event.content:
                    if isinstance(content_block, ToolUseBlock):
                        events.append(
                            ToolCall(
                                tool_call_id=content_block.id,
                                tool_name=content_block.name,
                                tool_args=content_block.input,
                                timestamp=timestamp,
                            )
                        )
            # Extract tool results from UserMessage if present
            elif isinstance(event, UserMessage):
                # UserMessage content can be str or list[ContentBlock]
                if isinstance(event.content, list):
                    for content_block in event.content:
                        if isinstance(content_block, ToolResultBlock):
                            # Convert content to string
                            if isinstance(content_block.content, list):
                                # Join text blocks from the content
                                text_parts = []
                                for item in content_block.content:
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
                                result_str = "\n".join(text_parts)
                            elif content_block.content is None:
                                result_str = ""
                            else:
                                result_str = str(content_block.content)

                            events.append(
                                ToolResult(
                                    tool_call_id=content_block.tool_use_id,
                                    result_content=result_str,
                                    is_error=content_block.is_error or False,
                                    timestamp=timestamp,
                                )
                            )

            elif isinstance(event, TextResponse):
                events.append(
                    ConversationMessage(
                        role=MessageRole.AGENT,
                        text_content=event.content,
                        timestamp=timestamp,
                    )
                )

            elif isinstance(event, VirtualToolRequests):
                # Virtual tool call requests - convert to ToolCallRequest events
                for call in event.calls:
                    events.append(
                        ToolCallRequest(
                            tool_call_id=call.tool_name,  # For virtual tools, tool_name is the ID
                            tool_name=call.tool_name,
                            tool_args=call.arguments,
                            timestamp=timestamp,
                        )
                    )

        # After execution, update session_id in conversation if it changed
        if agent.session_id != self.conversation.external_session_id:
            self.conversation_repo.update_external_session_id(self.conversation, agent.session_id)

        return events

    async def get_conversation_messages(self) -> list[ConversationEvent]:
        """Retrieve all events for the Claude Code conversation.

        Events are loaded from Claude Code session files and include text messages,
        tool calls, and tool results in chronological order.
        Claude Code manages its own session storage in ~/.claude/projects.

        Returns:
            List of ConversationEvent instances in chronological order.
            Returns empty list if no session_id (conversation hasn't started or was cleared).
        """
        # Return empty list if no session exists yet
        if not self.session_id:
            return []

        # Load low-level session messages
        claude_session_service = ClaudeCodeSessionService()
        session_messages = claude_session_service.load_session_messages(self.session_id)

        # Convert to conversation events with filtering
        return self._session_messages_to_events(session_messages)

    def _session_messages_to_events(self, session_messages: list[SessionMessage]) -> list[ConversationEvent]:
        """Convert session messages to conversation events.

        This method expands each SessionMessage.content list (which can contain multiple blocks)
        into separate events, providing a complete timeline of the conversation including
        tool calls and results.

        Filters out:
        - Sidechain messages
        - Invalid tool calls (malformed JSON that failed validation)

        Args:
            session_messages: List of session messages from Claude Code

        Returns:
            List of ConversationEvent instances (ConversationMessage, ToolCall, ToolResult)
        """
        events: list[ConversationEvent] = []

        for session_msg in session_messages:
            # Skip sidechain messages
            if session_msg.is_sidechain:
                continue

            # Process each content block in the message
            for content_block in session_msg.content:
                block_type = content_block["type"]

                if block_type == "text":
                    # Text content - parse to determine message type
                    text_content: str = content_block["text"]

                    # Parse the message to get its type
                    parsed = ClaudeResponseParser.parse_message(text_content)

                    if isinstance(parsed, TextResponse):
                        # Standard text message
                        conv_role = (
                            MessageRole.USER if session_msg.role == SessionMessageRole.USER else MessageRole.AGENT
                        )
                        events.append(
                            ConversationMessage(
                                role=conv_role,
                                text_content=parsed.content,
                                timestamp=session_msg.timestamp,
                            )
                        )

                    elif isinstance(parsed, VirtualToolCall):
                        # Virtual tool call - convert to ToolCall event (for both invalid and valid calls)
                        events.append(
                            ToolCall(
                                tool_call_id=parsed.tool_name,  # Use tool_name as ID for virtual tools
                                tool_name=parsed.tool_name,
                                tool_args=parsed.arguments,
                                timestamp=session_msg.timestamp,
                            )
                        )

                    elif isinstance(parsed, VirtualToolResult):
                        # Tool result - convert to ToolResult event
                        events.append(
                            ToolResult(
                                tool_call_id=parsed.tool_name,  # Use tool_name as ID for virtual tools
                                result_content=parsed.content,
                                is_error=not parsed.successful,
                                timestamp=session_msg.timestamp,
                            )
                        )

                elif block_type == "tool_use":
                    events.append(
                        ToolCall(
                            tool_call_id=content_block["id"],
                            tool_name=content_block["name"],
                            tool_args=content_block["input"],
                            timestamp=session_msg.timestamp,
                        )
                    )

                elif block_type == "tool_result":
                    result_content = content_block["content"]

                    # Convert content to string if it's a list of dicts
                    if isinstance(result_content, list):
                        # Join text blocks from the content
                        text_parts = []
                        for item in result_content:
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                        result_str = "\n".join(text_parts)
                    else:
                        result_str = str(result_content)

                    events.append(
                        ToolResult(
                            tool_call_id=content_block["tool_use_id"],
                            result_content=result_str,
                            is_error=content_block.get("is_error", False),
                            timestamp=session_msg.timestamp,
                        )
                    )

        return events
