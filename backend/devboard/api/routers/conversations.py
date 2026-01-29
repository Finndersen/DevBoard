"""Unified conversation API router."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines import AgentEngine
from devboard.agents.events import ConversationEvent
from devboard.api.dependencies.conversations import get_agent_conversation_service
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.repositories import get_conversation_repository
from devboard.api.dependencies.services import get_agent_config_service, get_workspace_allocation_service
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    ToolApprovals,
)
from devboard.api.schemas.common import DeleteResponse
from devboard.api.schemas.conversation import ConversationResponse
from devboard.api.schemas.integration import UpdateConversationModelRequest
from devboard.api.streaming import stream_conversation_events
from devboard.db.models import Conversation, Task, TaskStatus
from devboard.db.repositories import ConversationRepository
from devboard.services.workspace_allocation_service import WorkspaceAllocationService

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


@router.post("/{conversation_id}/messages/stream")
async def stream_conversation_message(
    request: ChatRequest,
    conversation: Conversation = Depends(get_verified_conversation),
    agent_conversation_service: BaseAgentConversationService = Depends(get_agent_conversation_service),
    workspace_allocation_service: WorkspaceAllocationService = Depends(get_workspace_allocation_service),
) -> StreamingResponse:
    """Stream conversation events as they are generated.

    Uses the appropriate agent engine (PydanticAI or Claude Code) based on
    the conversation's configuration.

    Returns events as newline-delimited JSON (NDJSON) for real-time updates.
    Each line is a JSON-serialized ConversationEvent.
    """
    # Check if parent task is complete - chat is disabled for completed tasks
    conversation_parent = conversation.get_parent_entity()
    if isinstance(conversation_parent, Task) and conversation_parent.status == TaskStatus.COMPLETE:
        raise HTTPException(status_code=400, detail="Cannot send messages for completed tasks")

    agent_event_stream = agent_conversation_service.stream_events_for_message_or_approval(request.message)
    if isinstance(conversation_parent, Task):
        agent_event_stream = workspace_allocation_service.run_task_agent_in_workspace(
            task=conversation_parent, agent_stream=agent_event_stream
        )

    return stream_conversation_events(agent_event_stream)


@router.post("/{conversation_id}/approve-tools/stream")
async def stream_approve_conversation_tools(
    request: ToolApprovals,
    conversation: Conversation = Depends(get_verified_conversation),
    agent_conversation_service: BaseAgentConversationService = Depends(get_agent_conversation_service),
    workspace_allocation_service: WorkspaceAllocationService = Depends(get_workspace_allocation_service),
) -> StreamingResponse:
    """Stream tool approval events as they are generated.

    Processes tool approval decisions and continues agent execution
    with the appropriate engine (PydanticAI or Claude Code).

    Returns events as newline-delimited JSON (NDJSON) for real-time updates.
    Each line is a JSON-serialized ConversationEvent.
    """
    # Check if parent task is complete - chat is disabled for completed tasks
    conversation_parent = conversation.get_parent_entity()
    if isinstance(conversation_parent, Task) and conversation_parent.status == TaskStatus.COMPLETE:
        raise HTTPException(status_code=400, detail="Cannot send messages for completed tasks")

    agent_event_stream = agent_conversation_service.stream_events_for_message_or_approval(request)
    if isinstance(conversation_parent, Task):
        agent_event_stream = workspace_allocation_service.run_task_agent_in_workspace(
            task=conversation_parent, agent_stream=agent_event_stream
        )

    return stream_conversation_events(agent_event_stream)


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
) -> dict[str, Any]:
    """Update the model for an active conversation.

    The model can be changed within the same engine (e.g., switching from
    Opus to Sonnet in Claude Code). The engine itself cannot be changed
    mid-conversation.
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
