"""Unified conversation API router."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.internal.agent_conversation import PydanticAIConversationService
from devboard.api.dependencies.agents import get_conversation_agent
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.repositories import get_conversation_repository
from devboard.api.dependencies.services import get_agent_config_service, get_conversation_service
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    ConversationMessage,
    PromptResponse,
    ToolApprovalRequest,
)
from devboard.api.schemas.common import DeleteResponse
from devboard.api.schemas.integration import UpdateConversationModelRequest
from devboard.db.models import Conversation
from devboard.db.repositories.conversation import ConversationRepository
from devboard.services.conversation_service import ConversationService

router = APIRouter()


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessage])
async def get_conversation_messages(
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> list[ConversationMessage]:
    """Get all messages for a conversation."""
    return await conversation_service.get_conversation_messages(conversation=conversation)


@router.post("/{conversation_id}/messages", response_model=PromptResponse)
async def send_conversation_message(
    conversation_id: int,
    request: ChatRequest,
    agent=Depends(get_conversation_agent),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> PromptResponse:
    """Send message to any conversation."""
    # Create service manually with the resolved dependencies
    conversation_service = PydanticAIConversationService(
        conversation_id=conversation_id, agent=agent, conversation_repository=conversation_repo
    )

    return await conversation_service.send_message(message=request.message)


@router.post("/{conversation_id}/approve-tools", response_model=PromptResponse)
async def approve_conversation_tools(
    conversation_id: int,
    request: ToolApprovalRequest,
    agent=Depends(get_conversation_agent),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> PromptResponse:
    """Approve tools for any conversation."""
    # Create service manually with the resolved dependencies
    conversation_service = PydanticAIConversationService(
        conversation_id=conversation_id, agent=agent, conversation_repository=conversation_repo
    )

    return await conversation_service.process_tool_approvals(approvals=request.approvals)


@router.delete("/{conversation_id}/messages", response_model=DeleteResponse)
async def clear_conversation_messages(
    conversation_id: int,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> DeleteResponse:
    """Clear all messages for a conversation."""
    deleted_count = conversation_repo.delete_messages(conversation_id)
    conversation_repo.db.commit()

    return DeleteResponse(
        message=f"Cleared {deleted_count} conversation messages",
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

    # Validate model compatible with conversation's engine
    engine_def = agent_config_service.engine_repository.get_engine_definition(conversation.engine)
    if request.model_id not in engine_def.available_models:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{request.model_id}' not compatible with engine '{conversation.engine.value}'. "
            f"Available models: {', '.join(engine_def.available_models)}",
        )

    # Validate model is available (provider configured)
    try:
        available_models = agent_config_service._get_available_models_for_engine(conversation.engine)
        if not any(m.id == request.model_id for m in available_models):
            raise HTTPException(
                status_code=400,
                detail=f"Model '{request.model_id}' not available. "
                f"Ensure the provider is configured with valid API credentials.",
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    # Update model
    try:
        updated = conversation_repo.update_model(conversation_id, request.model_id)
        conversation_repo.db.commit()

        return {
            "conversation_id": updated.id,
            "agent_role": updated.agent_role,
            "engine": updated.engine.value,
            "model_id": updated.model_id,
            "updated_at": updated.updated_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
