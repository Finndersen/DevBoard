"""PydanticAI agent conversation service with deferred tools support."""

import datetime

import logfire
from pydantic_ai import AgentRunResultEvent, FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.messages import AgentStreamEvent, ModelMessage, RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_ai.tools import (
    DeferredToolApprovalResult,
    DeferredToolRequests,
    DeferredToolResults,
    ToolApproved,
    ToolDenied,
)

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines.internal.base_agent import InternalAgent
from devboard.agents.engines.internal.deps import BaseDeps
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
from devboard.db.models.messages import ConversationMessage as DbConversationMessage
from devboard.db.models.messages import MessageType
from devboard.db.repositories.conversation import ConversationRepository


class PydanticAIConversationService(BaseAgentConversationService):
    """Service for handling internal PydanticAI agent conversations.

    This service manages conversations for PydanticAI-based agents, storing
    messages in the database and handling tool approval workflows.

    Attributes:
        conversation: The conversation instance (from base class)
        agent: The PydanticAI agent instance
        conversation_repo: Repository for database operations
    """

    def __init__(
        self,
        conversation: Conversation,
        agent: InternalAgent,
        conversation_repository: ConversationRepository,
    ):
        """Initialize PydanticAI conversation service.

        Args:
            conversation: The conversation instance to manage
            agent: The PydanticAI agent instance
            conversation_repository: Repository for conversation database operations
        """
        super().__init__(conversation, conversation_repository)
        self.agent = agent

    @property
    def conversation_id(self) -> int:
        """Get the conversation ID from the conversation instance."""
        return self.conversation.id

    async def send_message(
        self,
        message: str,
    ) -> list[ConversationEvent]:
        """Process a message and return conversation events.

        Args:
            message: User's message

        Returns:
            List of conversation events including tool calls, results, and final message
        """
        with logfire.span(
            "agent_conversation.send_message",
            conversation_id=self.conversation.id,
            message_length=len(message),
        ):
            return await self._handle_message_or_approval(message_or_approvals=message)

    async def process_tool_approvals(
        self,
        approvals: dict[str, ToolApprovalDecision],
    ) -> list[ConversationEvent]:
        """Process tool approval/denial and continue agent execution.

        Args:
            approvals: User's approval decisions

        Returns:
            List of conversation events including tool calls, results, and final message
        """
        with logfire.span(
            "agent_conversation.process_tool_approval",
            conversation_id=self.conversation.id,
            approval_count=len(approvals),
        ):
            tool_approval_results = self._create_deferred_results(approvals)
            return await self._handle_message_or_approval(message_or_approvals=tool_approval_results)

    async def _handle_message_or_approval(
        self, message_or_approvals: str | DeferredToolResults
    ) -> list[ConversationEvent]:
        """
        Handle either a new user message or tool approval result.
        :param message_or_approvals: User message/prompt or tool approval results
        :return: List of conversation events
        """
        # Load conversation history
        existing_messages = self._get_message_history()
        # Verify integrity of message history
        if isinstance(message_or_approvals, DeferredToolResults):
            if not existing_messages:
                raise ValueError("No existing messages found for processing tool approvals.")
            if existing_messages[-1].message_type != MessageType.TOOL_CALL:
                raise ValueError("Last message is not a tool call; cannot process approvals.")
        else:
            if existing_messages and existing_messages[-1].message_type == MessageType.TOOL_CALL:
                # If there was an issue processing tool approvals or they were never provided,
                # need to clear the message history until previous message
                delete_count = self.conversation_repo.delete_tool_approval_messages(self.conversation.id)
                existing_messages = existing_messages[:-delete_count]
                logfire.warning(f"Deleted {delete_count} messages due to missing tool approvals")

        message_history = self.conversation_repo.convert_messages_to_pydantic(existing_messages)

        # Process with agent using streaming
        events: list[ConversationEvent] = []
        agent_run_result = None

        async for event in self.agent.stream_events(
            prompt_or_approvals=message_or_approvals,
            conversation_history=message_history,
            deps=BaseDeps(),
        ):
            # Capture final result
            if isinstance(event, AgentRunResultEvent):
                agent_run_result = event.result
            else:
                # Collect events for batch processing
                converted_event = self._convert_stream_event(event)
                if converted_event is not None:
                    events.append(converted_event)

        if agent_run_result is None:
            raise ValueError("Agent execution did not produce a result")

        # Store and process results
        saved_messages = self._store_new_messages(new_messages=agent_run_result.new_messages())

        # Add final message or tool requests to events
        output = agent_run_result.output
        if isinstance(output, DeferredToolRequests):
            # Add tool requests to events
            timestamp = datetime.datetime.now(datetime.UTC)
            for tr in output.approvals:
                # Convert args to dict if it's a string (JSON-encoded)
                tool_args: dict | None = tr.args if isinstance(tr.args, dict) else None
                events.append(
                    ToolCallRequest(
                        tool_call_id=tr.tool_call_id,
                        tool_name=tr.tool_name,
                        tool_args=tool_args,
                        timestamp=timestamp,
                    )
                )
        elif isinstance(output, str):
            # Add final message to events
            agent_final_message = saved_messages[-1]
            events.append(
                ConversationMessage(
                    role=MessageRole.AGENT,
                    text_content=output,
                    timestamp=agent_final_message.timestamp,
                )
            )
        else:
            raise ValueError(f"Unexpected agent result: {output}")

        return events

    def _convert_stream_event(self, event: AgentStreamEvent) -> ConversationEvent | None:
        """Convert a PydanticAI stream event to our ConversationEvent type.

        Args:
            event: Stream event from PydanticAI

        Returns:
            ConversationEvent instance or None if this event type should be ignored
        """
        timestamp = datetime.datetime.now(datetime.UTC)

        if isinstance(event, FunctionToolCallEvent):
            # Extract tool call information
            part = event.part
            return ToolCall(
                tool_call_id=part.tool_call_id,
                tool_name=part.tool_name,
                tool_args=part.args,
                timestamp=timestamp,
            )

        elif isinstance(event, FunctionToolResultEvent):
            # Extract tool result information
            result_part = event.result
            is_error = isinstance(result_part, RetryPromptPart)
            result_content = str(result_part.content)

            return ToolResult(
                tool_call_id=result_part.tool_call_id,
                result_content=result_content,
                is_error=is_error,
                timestamp=timestamp,
            )

        # Ignore other event types:
        # - AgentRunResultEvent: Handled separately in main flow
        # - PartStartEvent, PartDeltaEvent: For future real-time streaming

        return None

    def _create_deferred_results(self, approvals: dict[str, ToolApprovalDecision]) -> DeferredToolResults:
        """Create deferred tool results from user approvals.

        Args:
            approvals: User's approval decisions

        Returns:
            PydanticAI DeferredToolResults object to continue agent execution
        """
        converted_approvals: dict[str, DeferredToolApprovalResult] = {}
        for tool_call_id, decision in approvals.items():
            if decision.approved:
                # For approved tools, set approval to True
                converted_approvals[tool_call_id] = ToolApproved()
                logfire.info(f"Tool {tool_call_id} approved")
            else:
                # For denied tools, set approval to False or use ToolDenied
                if decision.feedback:
                    message = f"Tool call DENIED with feedback: {decision.feedback}"
                else:
                    message = "The tool call was DENIED."

                converted_approvals[tool_call_id] = ToolDenied(message=message)
                logfire.info(f"Tool {tool_call_id} denied with feedback: {decision.feedback}")

        return DeferredToolResults(approvals=converted_approvals)

    def _get_message_history(self) -> list[DbConversationMessage]:
        return self.conversation_repo.get_messages(self.conversation.id)

    def _store_new_messages(self, new_messages: list[ModelMessage]) -> list[DbConversationMessage]:
        """Store new messages from agent result in DB."""
        # Extract all messages from the agent result
        saved_messages = []
        for message in new_messages:
            saved_messages.append(self.conversation_repo.create_message(self.conversation.id, message))
        return saved_messages

    async def get_conversation_messages(self) -> list[ConversationEvent]:
        """Retrieve all messages for the PydanticAI conversation.

        Messages are queried from the database and converted to ConversationEvent objects
        that include text messages, tool calls, and tool results.

        Returns:
            List of ConversationEvent instances in chronological order
        """
        db_messages = self.conversation_repo.get_messages(self.conversation.id)

        events: list[ConversationEvent] = []

        for msg in db_messages:
            # Convert each database message to appropriate ConversationEvent type(s)
            msg_events = self._db_message_to_events(msg)
            events.extend(msg_events)

        return events

    def _db_message_to_events(self, msg: DbConversationMessage) -> list[ConversationEvent]:
        """Convert a database message to one or more ConversationEvent objects.

        Args:
            msg: Database conversation message

        Returns:
            List of ConversationEvent objects representing the message content
        """
        events: list[ConversationEvent] = []

        if msg.message_type == MessageType.USER_PROMPT:
            # User prompt - single text message
            events.append(
                ConversationMessage(
                    role=MessageRole.USER,
                    text_content=msg.text_content,
                    timestamp=msg.timestamp,
                )
            )
        elif msg.message_type == MessageType.TEXT_RESPONSE:
            # Agent text response - single text message
            events.append(
                ConversationMessage(
                    role=MessageRole.AGENT,
                    text_content=msg.text_content,
                    timestamp=msg.timestamp,
                )
            )
        elif msg.message_type in (MessageType.TOOL_CALL, MessageType.TOOL_RESULT, MessageType.STRUCTURED_RESPONSE):
            # For messages containing tool calls/results, we need to parse the PydanticAI message
            pydantic_msg = self.conversation_repo.convert_messages_to_pydantic([msg])[0]
            # Extract parts from the message
            for part in pydantic_msg.parts:
                if isinstance(part, ToolCallPart):
                    events.append(
                        ToolCall(
                            tool_call_id=part.tool_call_id,
                            tool_name=part.tool_name,
                            tool_args=part.args,
                            timestamp=msg.timestamp,
                        )
                    )
                elif isinstance(part, ToolReturnPart):
                    events.append(
                        ToolResult(
                            tool_call_id=part.tool_call_id,
                            result_content=str(part.content),
                            is_error=False,
                            timestamp=msg.timestamp,
                        )
                    )

        return events
