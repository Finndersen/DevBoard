"""Shared service logic for agent conversations with deferred tools support."""

import logging

import logfire
from pydantic_ai.messages import ModelMessage
from pydantic_ai.tools import (
    DeferredToolApprovalResult,
    DeferredToolRequests,
    DeferredToolResults,
    ToolApproved,
    ToolDenied,
)

from devboard.agents.base_agent import BaseAgent
from devboard.agents.deps import BaseDeps
from devboard.api.schemas.agent_conversation import (
    ConversationMessage,
    MessageRole,
    PromptResponse,
    PromptResponseType,
    ToolApprovalDecision,
    ToolCallRequest,
)
from devboard.db.models.messages import ConversationMessage as DbConversationMessage
from devboard.db.models.messages import MessageType
from devboard.db.repositories.conversation import ConversationRepository

logger = logging.getLogger(__name__)


class AgentConversationService:
    """Service for handling agent conversations with shared logic."""

    def __init__(
        self,
        conversation_id: int,
        agent: BaseAgent,
        conversation_repository: ConversationRepository,
    ):
        self.conversation_id = conversation_id
        self.agent = agent
        self.conversation_repo = conversation_repository

    async def send_message(
        self,
        message: str,
    ) -> PromptResponse:
        """Process a message and return conversation response.

        Args:
            message: User's message
        """
        with logfire.span(
            "agent_conversation.send_message",
            conversation_id=self.conversation_id,
            message_length=len(message),
        ):
            return await self._handle_message_or_approval(message_or_approvals=message)

    async def process_tool_approvals(
        self,
        approvals: dict[str, ToolApprovalDecision],
    ) -> PromptResponse:
        """Process tool approval/denial and continue agent execution.

        Args:
            approvals: User's approval decisions
        """
        with logfire.span(
            "agent_conversation.process_tool_approval",
            conversation_id=self.conversation_id,
            approval_count=len(approvals),
        ):
            tool_approval_results = self._create_deferred_results(approvals)
            return await self._handle_message_or_approval(message_or_approvals=tool_approval_results)

    async def _handle_message_or_approval(self, message_or_approvals: str | DeferredToolResults) -> PromptResponse:
        """
        Handle either a new user message or tool approval result.
        :param message_or_approvals: User message/prompt or tool approval results
        :return:
        """
        # Load conversation history
        existing_messages = self.get_message_history()
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
                delete_count = self.conversation_repo.delete_tool_approval_messages(self.conversation_id)
                existing_messages = existing_messages[:-delete_count]
                logfire.warning(f"Deleted {delete_count} messages due to missing tool approvals")

        message_history = self.conversation_repo.convert_messages_to_pydantic(existing_messages)

        # Process with agent
        result = await self.agent.run(
            prompt_or_approvals=message_or_approvals,
            conversation_history=message_history,
            deps=BaseDeps(),
        )

        # Store and process results
        saved_messages = self.store_new_messages(new_messages=result.new_messages())

        output = result.output
        if isinstance(output, DeferredToolRequests):
            tool_requests = [
                ToolCallRequest(
                    tool_call_id=tr.tool_call_id,
                    tool_name=tr.tool_name,
                    tool_args=tr.args,
                )
                for tr in output.approvals
            ]
            response = PromptResponse(type=PromptResponseType.TOOL_REQUEST, tool_requests=tool_requests)
        elif isinstance(output, str):
            agent_final_message = saved_messages[-1]
            response = PromptResponse(
                type=PromptResponseType.MESSAGE,
                message=ConversationMessage(
                    id=agent_final_message.id,
                    role=MessageRole.AGENT,
                    text_content=output,
                    timestamp=agent_final_message.timestamp,
                ),
            )
        else:
            raise ValueError(f"Unexpected agent result: {output}")

        return response

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
                logger.info(f"Tool {tool_call_id} approved")
            else:
                # For denied tools, set approval to False or use ToolDenied
                if decision.feedback:
                    message = f"Tool call DENIED with feedback: {decision.feedback}"
                else:
                    message = "The tool call was DENIED."

                converted_approvals[tool_call_id] = ToolDenied(message=message)
                logger.info(f"Tool {tool_call_id} denied with feedback: {decision.feedback}")

        return DeferredToolResults(approvals=converted_approvals)

    def get_message_history(self) -> list[ConversationMessage]:
        return self.conversation_repo.get_messages(self.conversation_id)

    def store_new_messages(self, new_messages: list[ModelMessage]) -> list[DbConversationMessage]:
        """Store new messages from agent result in DB."""
        # Extract all messages from the agent result
        saved_messages = []
        for message in new_messages:
            saved_messages.append(self.conversation_repo.create_message(self.conversation_id, message))
        return saved_messages
