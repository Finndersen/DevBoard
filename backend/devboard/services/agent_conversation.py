"""Shared service logic for agent conversations with deferred tools support."""

import logging
from typing import Any

import logfire
from fastapi import HTTPException
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.run import AgentRunResult
from sqlalchemy.orm import Session

from devboard.agents.base_agent import BaseAgent
from devboard.api.schemas.agent_conversation import (
    ConversationMessageResponse,
    ConversationResponse,
    PendingApproval,
    ToolApprovalRequest,
)
from devboard.db.models.messages import BaseConversationMessage
from devboard.db.repositories.conversation_message import BaseConversationMessageRepository

logger = logging.getLogger(__name__)


class AgentConversationService:
    """Service for handling agent conversations with shared logic."""

    def __init__(self, agent: BaseAgent, message_type: type[BaseConversationMessage], message_repository: BaseConversationMessageRepository):
        self.agent = agent
        self.message_repo = message_repository
        self.message_type = message_type


    async def send_message(
        self,
        entity_id: int,
        message: str,
    ) -> ConversationResponse:
        """Process a message and return conversation response.

        Args:
            entity_id: ID of entity (task or project)
            message: User's message
            agent_service: Agent service to process with
            message_repo: Repository for message storage
            db: Database session
            **agent_kwargs: Additional arguments for agent processing
        """
        with logfire.span(
            "agent_conversation.send_message",
            entity_id=entity_id,
            message_length=len(message),
        ):
            try:
                # Load conversation history
                existing_messages = self.message_repo.get_all_for_entity(entity_id)
                message_history = self.convert_messages_to_pydantic(
                    existing_messages
                )

                # Process with agent
                result, deferred_requests = await self._process_with_agent(
                    agent_service,
                    message,
                    message_history,
                    entity_id=entity_id,
                    **agent_kwargs,
                )

                self.store_new_messages(result)


                # Convert to response format
                messages = self._convert_messages_to_response(
                    [saved_user_message, saved_agent_message]
                )

                # Extract pending approvals if any
                pending_approvals = None
                if deferred_requests:
                    pending_approvals = self._extract_pending_approvals(deferred_requests)

                return ConversationResponse(
                    messages=messages,
                    pending_approvals=pending_approvals,
                    conversation_complete=deferred_requests is None,
                )

            except Exception as e:
                db.rollback()
                logfire.error(
                    "Error processing message", entity_id=entity_id, error=str(e), exc_info=e
                )
                raise HTTPException(
                    status_code=500, detail=f"Error processing message: {str(e)}"
                ) from e

    async def process_tool_approval(
        self,
        entity_id: int,
        approval_request: ToolApprovalRequest,
        agent_service: BaseAgent,
        db: Session,
        create_message_model: callable,
        **agent_kwargs,
    ) -> ConversationResponse:
        """Process tool approval/denial and continue agent execution.

        Args:
            entity_id: ID of entity (task or project)
            approval_request: User's approval decisions
            agent_service: Agent service to continue with
            message_repo: Repository for message storage
            db: Database session
            create_message_model: Function to create message model instance
            **agent_kwargs: Additional arguments for agent processing
        """
        with logfire.span(
            "agent_conversation.process_tool_approval",
            entity_id=entity_id,
            approval_count=len(approval_request.approvals),
        ):
            try:
                # Load conversation history
                existing_messages = message_repo.get_by_entity_id(entity_id)
                message_history = agent_service.extract_message_history_from_records(
                    existing_messages
                )

                # Create deferred tool results from approvals
                deferred_results = self._create_deferred_results(approval_request)

                # Continue agent execution
                result = await self._process_tool_approval_with_agent(
                    agent_service,
                    deferred_results,
                    message_history,
                    entity_id=entity_id,
                    **agent_kwargs,
                )

                # Store continuation response
                agent_message_model = create_message_model(
                    message_type="response",
                    pydantic_content=agent_service.serialize_messages(result),
                )
                saved_agent_message = message_repo.create(agent_message_model)
                db.commit()

                # Convert to response format
                messages = self._convert_messages_to_response([saved_agent_message])

                return ConversationResponse(
                    messages=messages, pending_approvals=None, conversation_complete=True
                )

            except Exception as e:
                db.rollback()
                logfire.error(
                    "Error processing tool approval", entity_id=entity_id, error=str(e), exc_info=e
                )
                raise HTTPException(
                    status_code=500, detail=f"Error processing tool approval: {str(e)}"
                ) from e

    async def _process_with_agent(
        self, agent_service: BaseAgent, message: str, history: list, **kwargs
    ) -> tuple[Any, Any]:
        """Process message with appropriate agent service."""
        # This would call different methods based on agent type
        # For now, return a placeholder
        raise NotImplementedError("Subclasses must implement agent processing")

    async def _process_tool_approval_with_agent(
        self, agent_service: BaseAgent, deferred_results: Any, history: list, **kwargs
    ) -> Any:
        """Process tool approval with appropriate agent service."""
        # This would call different methods based on agent type
        # For now, return a placeholder
        raise NotImplementedError("Subclasses must implement tool approval processing")

    def _convert_messages_to_response(
        self, messages: list[BaseConversationMessage]
    ) -> list[ConversationMessageResponse]:
        """Convert database messages to response format."""
        response_messages = []
        for msg in messages:
            # Extract text content from pydantic_content
            text_content = None
            tool_calls = None

            if isinstance(msg.pydantic_content, dict):
                if msg.message_type == "request":
                    text_content = msg.pydantic_content.get("content")
                elif msg.message_type == "response":
                    # For response messages, extract text from the response
                    if "data" in msg.pydantic_content:
                        text_content = msg.pydantic_content["data"]
                    # TODO: Extract tool call information

            response_messages.append(
                ConversationMessageResponse(
                    id=msg.id,
                    message_type=msg.message_type,
                    text_content=text_content,
                    tool_calls=tool_calls,
                    created_at=msg.created_at,
                )
            )

        return response_messages

    def _extract_pending_approvals(self, deferred_requests: Any) -> list[PendingApproval]:
        """Extract pending approvals from deferred tool requests.

        Args:
            deferred_requests: PydanticAI DeferredToolRequests object

        Returns:
            List of pending approvals for frontend display
        """
        from devboard.services.document_editor import DocumentEditorService

        pending_approvals = []

        # DeferredToolRequests has 'approvals' attribute containing tools requiring approval
        if not hasattr(deferred_requests, 'approvals'):
            return pending_approvals

        for tool_request in deferred_requests.approvals:
            tool_call_id = tool_request.tool_call_id
            tool_name = tool_request.tool_name
            tool_args = tool_request.args

            # Handle document editing tools
            if tool_name.startswith("edit_"):
                document_type = tool_name.replace("edit_", "")
                edits = tool_args.get("edits", [])
                reasoning = tool_args.get("reasoning", "")

                # Generate diff preview using DocumentEditorService
                editor_service = DocumentEditorService()
                try:
                    # Get current content - for now we'll handle this later
                    # TODO: Extract current content from agent context or pass it in
                    current_content = ""

                    if current_content and edits:
                        # Apply edits to check for errors and generate diff
                        apply_result = editor_service.apply_edits(current_content, edits)
                        if apply_result.success:
                            # TODO: Replace with actual diff generation when available
                            diff_preview = self._create_basic_diff_preview(edits)
                        else:
                            # Show validation errors
                            error_messages = "\n".join(apply_result.errors)
                            diff_preview = f"Validation failed:\n{error_messages}"
                    else:
                        # Create a basic preview from the edits
                        diff_preview = self._create_basic_diff_preview(edits)

                except Exception as e:
                    diff_preview = f"Error generating diff: {str(e)}"

                pending_approvals.append(
                    PendingApproval(
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                        document_type=document_type,
                        edits=edits,
                        diff_preview=diff_preview,
                        reasoning=reasoning,
                    )
                )
            else:
                # Handle other tool types
                pending_approvals.append(
                    PendingApproval(
                        tool_call_id=tool_call_id,
                        tool_name=tool_name,
                        reasoning=tool_args.get("reasoning", ""),
                    )
                )

        return pending_approvals

    def _create_basic_diff_preview(self, edits: list) -> str:
        """Create a basic diff preview from document edits.

        Args:
            edits: List of DocumentEdit objects

        Returns:
            Basic string representation of the edits
        """
        if not edits:
            return "No edits specified"

        preview_lines = []
        for i, edit in enumerate(edits, 1):
            find_text = edit.get("find", "") if isinstance(edit, dict) else getattr(edit, "find", "")
            replace_text = edit.get("replace", "") if isinstance(edit, dict) else getattr(edit, "replace", "")

            preview_lines.append(f"Edit {i}:")
            preview_lines.append(f"- Find: {find_text[:100]}{'...' if len(find_text) > 100 else ''}")
            preview_lines.append(f"+ Replace: {replace_text[:100]}{'...' if len(replace_text) > 100 else ''}")
            preview_lines.append("")

        return "\n".join(preview_lines)

    def _create_deferred_results(self, approval_request: ToolApprovalRequest) -> Any:
        """Create deferred tool results from user approvals.

        Args:
            approval_request: User's approval decisions

        Returns:
            PydanticAI DeferredToolResults object to continue agent execution
        """
        try:
            from pydantic_ai import DeferredToolResults
        except ImportError:
            # Fallback for testing or if PydanticAI not available
            logger.warning("PydanticAI not available, creating mock deferred results")
            return approval_request

        # Create DeferredToolResults with approvals
        results = DeferredToolResults()

        for tool_call_id, decision in approval_request.approvals.items():
            if decision.approved:
                # For approved tools, set approval to True
                results.approvals[tool_call_id] = True
                # Optionally include feedback as data
                if decision.feedback:
                    logger.info(f"Tool {tool_call_id} approved with feedback: {decision.feedback}")
            else:
                # For denied tools, set approval to False or use ToolDenied
                results.approvals[tool_call_id] = False
                # Log the denial reason
                if decision.feedback:
                    logger.info(f"Tool {tool_call_id} denied with feedback: {decision.feedback}")

        return results

    def convert_messages_to_pydantic(self, message_records: list[BaseConversationMessage]) -> list[ModelMessage]:
        """Extract PydanticAI message history from database records."""
        # Extract pydantic_content from each record
        serialized_messages = [record.pydantic_content for record in message_records]

        if not serialized_messages:
            return []

        # Deserialize the messages
        messages = ModelMessagesTypeAdapter.validate_python(serialized_messages)
        return messages

    def store_new_messages(self, agent_result: AgentRunResult, entity_id: int) -> None:
        """Store new messages from agent result in DB."""
        # Extract all messages from the agent result
        for message in agent_result.new_messages():
            db_message = self.message_type.from_pydantic_message(entity_id, message)
            self.message_repo.create(db_message)




