"""Claude Code agent conversation service with virtual tool calling."""

import datetime
import re

import logfire
from claude_agent_sdk import AssistantMessage, ToolResultBlock, ToolUseBlock, UserMessage
from mcp.server.fastmcp.exceptions import ValidationError

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines.claude_code.base_agent import ClaudeCodeAgent, MessageResponse, VirtualToolRequests
from devboard.agents.engines.claude_code.message_parser import ClaudeMessageType, ClaudeResponseParser
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionService, SessionMessage, SessionMessageRole
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

        # Stream events from agent
        async for event in self.agent.stream_events(prompt_or_approvals=prompt_or_approvals):
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

            elif isinstance(event, MessageResponse):
                # Final message response - convert to ConversationMessage
                # Filter out validation errors and virtual tool calls
                message_type = ClaudeResponseParser.detect_message_type(event.content)
                if message_type == ClaudeMessageType.MESSAGE:
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
        if self.agent.session_id != self.conversation.external_session_id:
            self.conversation_repo.update_external_session_id(self.conversation, self.agent.session_id)

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
                    # Text content - check message type to determine how to handle
                    # Type guard: we know this is a TextBlockDict
                    if "text" in content_block:
                        text_content: str = content_block["text"]  # type: ignore[typeddict-item]
                        message_type = ClaudeResponseParser.detect_message_type(text_content)

                        if message_type == ClaudeMessageType.MESSAGE:
                            # Standard text message
                            conv_role = (
                                MessageRole.USER if session_msg.role == SessionMessageRole.USER else MessageRole.AGENT
                            )

                            events.append(
                                ConversationMessage(
                                    role=conv_role,
                                    text_content=text_content,
                                    timestamp=session_msg.timestamp,
                                )
                            )

                        elif message_type == ClaudeMessageType.TOOL_CALL:
                            # Virtual tool call - parse and convert to ToolCall event
                            try:
                                parsed = ClaudeResponseParser.parse_message(text_content)
                                if isinstance(parsed, str):
                                    raise ValueError("Expected VirtualToolCall data for TOOL_CALL message type")

                                tool_call = ToolCall(
                                    tool_call_id=parsed.tool_name,  # Use tool_name as ID for virtual tools
                                    tool_name=parsed.tool_name,
                                    tool_args=parsed.arguments,
                                    timestamp=session_msg.timestamp,
                                )
                            except ValidationError:
                                tool_call = ToolCall(
                                    tool_call_id="invalid_tool_call",
                                    tool_name="invalid_tool_call",
                                    tool_args=None,
                                    timestamp=session_msg.timestamp,
                                )

                            events.append(tool_call)

                        elif message_type == ClaudeMessageType.TOOL_RESULT:
                            # Tool result - convert to ToolResult event
                            # Extract tool name and result content
                            tool_info = ClaudeResponseParser.extract_tool_result_info(text_content)
                            if not tool_info:
                                raise ValueError("Failed to extract tool result information from text content")
                            tool_name, result_text = tool_info
                            events.append(
                                ToolResult(
                                    tool_call_id=tool_name,  # Use tool_name as ID for virtual tools
                                    result_content=result_text,
                                    is_error=False,
                                    timestamp=session_msg.timestamp,
                                )
                            )
                        elif message_type == ClaudeMessageType.VALIDATION_ERROR:
                            # Validation error - extract tool name (if present) and error message
                            error_info = ClaudeResponseParser.extract_validation_error_info(text_content)
                            if error_info:
                                tool_name_from_error, error_text = error_info
                                # Use tool_name from error tag if present, otherwise use generic ID
                                tool_call_id = tool_name_from_error if tool_name_from_error else "invalid_tool_call"
                                events.append(
                                    ToolResult(
                                        tool_call_id=tool_call_id,
                                        result_content=error_text,
                                        is_error=True,
                                        timestamp=session_msg.timestamp,
                                    )
                                )

                elif block_type == "tool_use":
                    # Type guard: we know this is a ToolUseBlockDict
                    if "id" in content_block and "name" in content_block and "input" in content_block:
                        events.append(
                            ToolCall(
                                tool_call_id=content_block["id"],  # type: ignore[typeddict-item]
                                tool_name=content_block["name"],  # type: ignore[typeddict-item]
                                tool_args=content_block["input"],  # type: ignore[typeddict-item]
                                timestamp=session_msg.timestamp,
                            )
                        )

                elif block_type == "tool_result":
                    # Type guard: we know this is a ToolResultBlockDict
                    if "tool_use_id" in content_block and "content" in content_block:
                        result_content = content_block["content"]  # type: ignore[typeddict-item]

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
                                tool_call_id=content_block["tool_use_id"],  # type: ignore[typeddict-item]
                                result_content=result_str,
                                is_error=content_block.get("is_error", False),
                                timestamp=session_msg.timestamp,
                            )
                        )

        return events

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

        # Skip sidechain messages
        if session_msg.is_sidechain:
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
