"""Shared service logic for agent conversations with deferred tools support."""

import logging

import logfire
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.tools import (
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
from devboard.db.models.messages import BaseConversationMessage
from devboard.db.repositories.conversation_message import (
    BaseConversationMessageRepository,
)

logger = logging.getLogger(__name__)


class AgentConversationService:
    """Service for handling agent conversations with shared logic."""

    def __init__(
        self,
        message_repository: BaseConversationMessageRepository,
    ):
        self.message_repo = message_repository

    async def send_message(
        self,
        agent: BaseAgent,
        message: str,
        entity_id: int,
    ) -> PromptResponse:
        """Process a message and return conversation response.

        Args:
            agent: The agent to use for processing
            entity_id: ID of entity (task or project)
            message: User's message
        """
        with logfire.span(
            "agent_conversation.send_message",
            entity_id=entity_id,
            message_length=len(message),
        ):
            return await self._handle_message_or_approval(
                agent=agent, entity_id=entity_id, message_or_approvals=message
            )

    async def process_tool_approvals(
        self,
        agent: BaseAgent,
        approvals: dict[str, ToolApprovalDecision],
        entity_id: int,
    ) -> PromptResponse:
        """Process tool approval/denial and continue agent execution.

        Args:
            agent: The agent to use for processing
            entity_id: ID of entity (task or project)
            approvals: User's approval decisions
        """
        with logfire.span(
            "agent_conversation.process_tool_approval",
            entity_id=entity_id,
            approval_count=len(approvals),
        ):
            tool_approval_results = self._create_deferred_results(approvals)
            return await self._handle_message_or_approval(
                agent=agent, entity_id=entity_id, message_or_approvals=tool_approval_results
            )

    async def _handle_message_or_approval(
        self, agent: BaseAgent, entity_id: int, message_or_approvals: str | DeferredToolResults
    ) -> PromptResponse:
        """
        Handle either a new user message or tool approval result.
        :param agent: The agent to use for processing
        :param entity_id: ID of entity (task or project)
        :param message_or_approvals: User message/prompt or tool approval results
        :return:
        """
        # Load conversation history
        existing_messages = self.message_repo.get_all_for_entity(entity_id)
        message_history = self.convert_messages_to_pydantic(existing_messages)

        # Process with agent
        result = await agent.run(
            prompt_or_approvals=message_or_approvals,
            message_history=message_history,
            deps=BaseDeps(),
        )

        # Store and process results
        saved_messages = self.store_new_messages(
            new_messages=result.new_messages(), entity_id=entity_id
        )

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
            response = PromptResponse(
                type=PromptResponseType.TOOL_REQUEST, tool_requests=tool_requests
            )
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

    def _create_deferred_results(
        self, approvals: dict[str, ToolApprovalDecision]
    ) -> DeferredToolResults:
        """Create deferred tool results from user approvals.

        Args:
            approvals: User's approval decisions

        Returns:
            PydanticAI DeferredToolResults object to continue agent execution
        """
        converted_approvals = {}
        for tool_call_id, decision in approvals.items():
            if decision.approved:
                # For approved tools, set approval to True
                converted_approvals[tool_call_id] = ToolApproved()
                logger.info(f"Tool {tool_call_id} approved")
            else:
                # For denied tools, set approval to False or use ToolDenied
                converted_approvals[tool_call_id] = ToolDenied(
                    message=decision.feedback or "The tool call was denied."
                )
                logger.info(f"Tool {tool_call_id} denied with feedback: {decision.feedback}")

        return DeferredToolResults(approvals=converted_approvals)

    def convert_messages_to_pydantic(
        self, message_records: list[BaseConversationMessage]
    ) -> list[ModelMessage]:
        """Extract PydanticAI message history from database records."""
        # Extract pydantic_content from each record
        serialized_messages = [record.pydantic_content for record in message_records]

        if not serialized_messages:
            return []

        # Deserialize the messages
        messages = ModelMessagesTypeAdapter.validate_python(serialized_messages)
        return messages

    def store_new_messages(
        self, new_messages: list[ModelMessage], entity_id: int
    ) -> list[BaseConversationMessage]:
        """Store new messages from agent result in DB."""
        # Extract all messages from the agent result
        saved_messages = []
        for message in new_messages:
            db_message = self.message_repo.MESSAGE_MODEL.from_pydantic_message(entity_id, message)
            saved_messages.append(self.message_repo.create(db_message))
        return saved_messages
