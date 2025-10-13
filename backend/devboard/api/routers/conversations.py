"""Unified conversation API router."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.types import AgentEngine
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.repositories import get_conversation_repository
from devboard.api.dependencies.services import get_agent_config_service, get_agent_conversation_service
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    ConversationMessage,
    PromptResponse,
    ToolApprovalRequest,
)
from devboard.api.schemas.common import DeleteResponse
from devboard.api.schemas.conversation import ConversationResponse
from devboard.api.schemas.integration import UpdateConversationModelRequest
from devboard.db.models import Conversation
from devboard.db.repositories.conversation import ConversationRepository

router = APIRouter()


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation: Conversation = Depends(get_verified_conversation),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
) -> ConversationResponse:
    """Get conversation details including model display name.

    Returns conversation configuration and metadata. The model_name field provides
    a human-readable display name derived from the model_id.
    """
    # Get model info for display name
    try:
        model = agent_config_service.llm_repository.get_model_by_id(conversation.model_id)
        model_name = model.name
    except ValueError:
        # Model not found in repository (shouldn't happen but handle gracefully)
        model_name = conversation.model_id

    return ConversationResponse(
        id=conversation.id,
        parent_entity_type=conversation.parent_entity_type.value,
        parent_entity_id=conversation.parent_entity_id,
        agent_role=conversation.agent_role,
        engine=conversation.engine.value,
        model_id=conversation.model_id,
        model_name=model_name,
        is_active=conversation.is_active,
        created_at=conversation.created_at,
    )


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessage])
async def get_conversation_messages(
    conversation_service: BaseAgentConversationService = Depends(get_agent_conversation_service),
) -> list[ConversationMessage]:
    """Get all messages for a conversation.

    Retrieves messages from database (PydanticAI) or session files (Claude Code)
    depending on the conversation's engine configuration.
    """
    return await conversation_service.get_conversation_messages()


@router.post("/{conversation_id}/messages", response_model=PromptResponse)
async def send_conversation_message(
    request: ChatRequest,
    conversation_service: BaseAgentConversationService = Depends(get_agent_conversation_service),
) -> PromptResponse:
    """Send message to any conversation.

    Uses the appropriate agent engine (PydanticAI or Claude Code) based on
    the conversation's configuration.
    """
    return await conversation_service.send_message(message=request.message)


@router.post("/{conversation_id}/approve-tools", response_model=PromptResponse)
async def approve_conversation_tools(
    request: ToolApprovalRequest,
    conversation_service: BaseAgentConversationService = Depends(get_agent_conversation_service),
) -> PromptResponse:
    """Approve or deny tool calls for any conversation.

    Processes tool approval decisions and continues agent execution
    with the appropriate engine (PydanticAI or Claude Code).
    """
    return await conversation_service.process_tool_approvals(approvals=request.approvals)


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

    # Validate model is available for the conversation's engine (provider configured)
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
