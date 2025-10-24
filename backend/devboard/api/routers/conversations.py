"""Unified conversation API router."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.events import ConversationEvent
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.repositories import get_conversation_repository
from devboard.api.dependencies.services import (
    get_agent_config_service,
    get_agent_conversation_service,
    get_prompt_action_service,
)
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    ToolApprovals,
)
from devboard.api.schemas.common import DeleteResponse
from devboard.api.schemas.conversation import ConversationResponse
from devboard.api.schemas.integration import UpdateConversationModelRequest
from devboard.api.schemas.prompt_action import PromptActionRequest
from devboard.db.models import Conversation
from devboard.db.repositories.conversation import ConversationRepository
from devboard.services.prompt_action_service import PromptActionNotFoundError, PromptActionService

router = APIRouter()


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation: Conversation = Depends(get_verified_conversation),
) -> ConversationResponse:
    """Get conversation details.

    Returns conversation configuration and metadata.
    """
    return ConversationResponse(
        id=conversation.id,
        parent_entity_type=conversation.parent_entity_type,
        parent_entity_id=conversation.parent_entity_id,
        agent_role=conversation.agent_role,
        engine=conversation.engine,
        model_id=conversation.model_id,
        is_active=conversation.is_active,
        external_session_id=conversation.external_session_id,
        created_at=conversation.created_at,
    )


@router.get("/{conversation_id}/messages", response_model=list[ConversationEvent])
async def get_conversation_messages(
    conversation_service: BaseAgentConversationService = Depends(get_agent_conversation_service),
) -> list[ConversationEvent]:
    """Get all messages for a conversation.

    Retrieves messages from database (PydanticAI) or session files (Claude Code)
    depending on the conversation's engine configuration.

    Note: ToolCallRequest events are excluded as they are ephemeral approval
    requests, not conversation history.
    """
    return await conversation_service.get_conversation_messages()


@router.post("/{conversation_id}/messages", response_model=list[ConversationEvent])
async def send_conversation_message(
    request: ChatRequest,
    conversation_service: BaseAgentConversationService = Depends(get_agent_conversation_service),
) -> list[ConversationEvent]:
    """Send message to any conversation.

    Uses the appropriate agent engine (PydanticAI or Claude Code) based on
    the conversation's configuration.

    Returns all events generated from processing the message, including
    tool calls, tool results, and the final response message.
    """
    return await conversation_service.send_message_or_approval(message_or_approvals=request.message)


@router.post("/{conversation_id}/approve-tools", response_model=list[ConversationEvent])
async def approve_conversation_tools(
    request: ToolApprovals,
    conversation_service: BaseAgentConversationService = Depends(get_agent_conversation_service),
) -> list[ConversationEvent]:
    """Approve or deny tool calls for any conversation.

    Processes tool approval decisions and continues agent execution
    with the appropriate engine (PydanticAI or Claude Code).

    Returns all events generated from processing the approvals, including
    tool calls, tool results, and the final response message.
    """
    return await conversation_service.send_message_or_approval(message_or_approvals=request)


@router.delete("/{conversation_id}/messages", response_model=DeleteResponse)
async def clear_conversation_messages(
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> DeleteResponse:
    """Clear all messages for a conversation.

    For INTERNAL engine conversations: Deletes messages from database.
    For Claude Code conversations: Resets external_session_id to start new session.
    """
    if conversation.engine == AgentEngine.CLAUDE_CODE:
        # Reset session ID for Claude Code conversations
        conversation_repo.update_external_session_id(conversation, None)
    else:
        # Delete database messages for INTERNAL engine
        conversation_repo.delete_messages(conversation.id)

    return DeleteResponse(
        message="Cleared conversation history.",
        success=True,
    )


@router.put("/{conversation_id}/model")
async def update_conversation_model(
    conversation_id: int,
    request: UpdateConversationModelRequest,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
) -> dict:
    """Update the model for an active conversation.

    The model can be changed within the same engine (e.g., switching from
    Opus to Sonnet in Claude Code). The engine itself cannot be changed
    mid-conversation.

    Args:
        conversation_id: ID of the conversation to update
        request: Request with new model_id
        conversation_repo: Conversation repository
        agent_config_service: Agent configuration service

    Returns:
        Updated conversation details

    Raises:
        HTTPException: 404 if conversation not found
        HTTPException: 400 if validation fails
    """
    # Get conversation
    conversation = conversation_repo.get_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if conversation is active
    if not conversation.is_active:
        raise HTTPException(status_code=400, detail="Cannot update model for archived conversation")

    # Validate model is available for the conversation's engine
    # None is allowed for engines that don't require model selection
    if request.model_id is not None:
        available_models_by_engine = agent_config_service.get_available_models_by_engine()
        engine_models = available_models_by_engine.models_by_engine.get(conversation.engine.value, [])

        if not any(m.id == request.model_id for m in engine_models):
            raise HTTPException(
                status_code=400,
                detail=f"Model '{request.model_id}' not available for engine '{conversation.engine.value}'. "
                f"Ensure the provider is configured with valid API credentials.",
            )

    # Update model
    updated = conversation_repo.update_model(conversation, request.model_id)

    return {
        "conversation_id": updated.id,
        "agent_role": updated.agent_role,
        "engine": updated.engine.value,
        "model_id": updated.model_id,
    }


@router.post("/{conversation_id}/prompt-action", response_model=list[ConversationEvent])
async def execute_prompt_action(
    request: PromptActionRequest,
    prompt_action_service: PromptActionService = Depends(get_prompt_action_service),
    conversation: Conversation = Depends(get_verified_conversation),
) -> list[ConversationEvent]:
    """Execute a predefined prompt action on a conversation.

    Prompt actions are reusable, named operations that send predefined prompts
    to agent conversations. This endpoint looks up the action by key and sends
    the associated prompt as a user message.

    Args:
        request: Request with action_key to execute
        prompt_action_service: Service for managing prompt actions
        conversation: Agent conversation

    Returns:
        List of ConversationEvent objects from processing the prompt action

    Raises:
        HTTPException: 404 if action_key not found
        HTTPException: 400 if conversation not active
    """
    # Check if conversation is active
    if not conversation.is_active:
        raise HTTPException(status_code=400, detail="Cannot execute prompt action on archived conversation")

    try:
        return await prompt_action_service.execute_action(request.action_key)
    except PromptActionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
