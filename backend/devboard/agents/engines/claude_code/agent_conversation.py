"""Claude Code agent conversation service with virtual tool calling."""

from collections.abc import AsyncIterator

import logfire

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines.claude_code.agent import ClaudeCodeAgent
from devboard.agents.engines.claude_code.message_parser import (
    ClaudeResponseParser,
    TextResponse,
    VirtualToolCall,
    VirtualToolResult,
    convert_virtual_tool_call_to_events,
)
from devboard.agents.engines.claude_code.session import (
    ClaudeCodeSessionService,
    SessionMessage,
    SessionMessageRole,
)
from devboard.agents.events import ConversationEvent, MessageRole, TextMessage, ToolCall, ToolResult
from devboard.agents.language_models import llm_registry
from devboard.agents.roles.base import Role
from devboard.api.schemas.agent_conversation import (
    ToolApprovals,
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
        super().__init__(conversation, role, conversation_repository)
        self.codebase_path = codebase_path

    @property
    def session_id(self) -> str | None:
        """Get the current Claude session ID from the conversation."""
        return self.conversation.external_session_id

    async def stream_events_for_message_or_approval(
        self,
        message_or_approvals: str | ToolApprovals,
    ) -> AsyncIterator[ConversationEvent]:
        """Stream conversation events from agent execution.

        Args:
            message_or_approvals: Either a user message string or ToolApprovals model

        Yields:
            ConversationEvent instances as they are generated during agent execution
        """
        is_approval = isinstance(message_or_approvals, ToolApprovals)

        with logfire.span(
            "claude_code_conversation.stream_events_for_message_or_approval",
            conversation_id=self.conversation.id,
            is_approval=is_approval,
        ):
            # Check session ID for approvals
            if is_approval and not self.session_id:
                raise ValueError("No session ID available - cannot process tool approvals")

            # Get model from conversation
            model = llm_registry.get(self.conversation.model_id) if self.conversation.model_id else None

            # Create agent with session_id
            agent = ClaudeCodeAgent(
                role=self.role,
                model=model,
                session_id=self.conversation.external_session_id,
                codebase_path=self.codebase_path,
            )

            # Stream events from agent execution
            async for event in agent.stream_events(message_or_approvals):
                yield event

            # Update session_id if changed
            if agent.session_id != self.conversation.external_session_id:
                self.conversation_repo.update_external_session_id(self.conversation, agent.session_id)

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
                    parsed = ClaudeResponseParser.parse_message_content(text_content)

                    if isinstance(parsed, TextResponse):
                        # Standard text message
                        conv_role = (
                            MessageRole.USER if session_msg.role == SessionMessageRole.USER else MessageRole.AGENT
                        )
                        events.append(
                            TextMessage(
                                role=conv_role,
                                text_content=parsed.content,
                                timestamp=session_msg.timestamp,
                            )
                        )

                    elif isinstance(parsed, VirtualToolCall):
                        # Virtual tool call - convert to ToolCall event (for both invalid and valid calls)
                        # Use helper function to convert to events
                        # Use ToolCall (not ToolCallRequest) since this is historical data from session
                        tool_call_events = convert_virtual_tool_call_to_events(
                            tool_call=parsed,
                            timestamp=session_msg.timestamp,
                            use_tool_call_request=False,
                        )
                        events.extend(tool_call_events)

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
