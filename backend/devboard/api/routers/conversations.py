"""Unified conversation API router."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.agent_execution import AgentExecutionService
from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.engines import AgentEngine
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionService
from devboard.agents.events import ConversationEvent
from devboard.api.dependencies.conversations import get_agent_execution_service, get_conversation_history_service
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.repositories import get_conversation_repository
from devboard.api.dependencies.services import (
    get_agent_config_service,
    get_conversation_service,
    get_workspace_allocation_service,
)
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    ToolApprovals,
)
from devboard.api.schemas.claude_code_todo import TodoItem
from devboard.api.schemas.common import ResetConversationResponse
from devboard.api.schemas.conversation import ConversationResponse
from devboard.api.schemas.integration import UpdateConversationModelRequest
from devboard.api.streaming import stream_conversation_events
from devboard.db.models import Conversation, ParentEntityType, Task, TaskStatus
from devboard.db.repositories import ConversationRepository
from devboard.services.conversation_service import ConversationService
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
    history_service: ConversationHistoryService = Depends(get_conversation_history_service),
) -> list[ConversationEvent]:
    """Get all messages for a conversation.

    Retrieves messages from database (PydanticAI) or session files (Claude Code)
    depending on the conversation's engine configuration.

    Note: ToolCallRequest events are excluded as they are ephemeral approval
    requests, not conversation history.
    """
    return await history_service.get_conversation_messages()


async def _stream_agent_response(
    http_request: Request,
    conversation: Conversation,
    agent_execution_service: AgentExecutionService,
    workspace_allocation_service: WorkspaceAllocationService,
    message_or_approvals: str | ToolApprovals,
) -> StreamingResponse:
    """Stream agent response events for a conversation.

    Handles both new messages and tool approval continuations.
    For Task conversations, wraps the stream with workspace allocation.
    """
    conversation_parent = conversation.get_parent_entity()
    if isinstance(conversation_parent, Task) and conversation_parent.status == TaskStatus.COMPLETE:
        raise HTTPException(status_code=400, detail="Cannot send messages for completed tasks")

    agent_event_stream = agent_execution_service.stream_events_for_message_or_approval(message_or_approvals)

    if isinstance(conversation_parent, Task):
        agent_event_stream = workspace_allocation_service.run_task_agent_in_workspace(
            task=conversation_parent, agent_stream=agent_event_stream
        )

    return stream_conversation_events(agent_event_stream, http_request)


@router.post("/{conversation_id}/messages/stream")
async def stream_conversation_message(
    http_request: Request,
    request: ChatRequest,
    conversation: Conversation = Depends(get_verified_conversation),
    agent_execution_service: AgentExecutionService = Depends(get_agent_execution_service),
    workspace_allocation_service: WorkspaceAllocationService = Depends(get_workspace_allocation_service),
) -> StreamingResponse:
    """Stream conversation events as they are generated.

    Uses the appropriate agent engine (PydanticAI or Claude Code) based on
    the conversation's configuration.

    Returns events as newline-delimited JSON (NDJSON) for real-time updates.
    Each line is a JSON-serialized ConversationEvent.
    """
    return await _stream_agent_response(
        http_request, conversation, agent_execution_service, workspace_allocation_service, request.message
    )


@router.post("/{conversation_id}/approve-tools/stream")
async def stream_approve_conversation_tools(
    http_request: Request,
    request: ToolApprovals,
    conversation: Conversation = Depends(get_verified_conversation),
    agent_execution_service: AgentExecutionService = Depends(get_agent_execution_service),
    workspace_allocation_service: WorkspaceAllocationService = Depends(get_workspace_allocation_service),
) -> StreamingResponse:
    """Stream tool approval events as they are generated.

    Processes tool approval decisions and continues agent execution
    with the appropriate engine (PydanticAI or Claude Code).

    Returns events as newline-delimited JSON (NDJSON) for real-time updates.
    Each line is a JSON-serialized ConversationEvent.
    """
    return await _stream_agent_response(
        http_request, conversation, agent_execution_service, workspace_allocation_service, request
    )


@router.post("/{conversation_id}/reset", response_model=ResetConversationResponse)
async def reset_conversation(
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ResetConversationResponse:
    """Reset a conversation by deleting it and creating a new one.

    This endpoint:
    1. Deletes the existing conversation (messages cascade delete)
    2. Creates a new conversation for the same parent entity
    3. Re-evaluates agent configuration, allowing updated settings to take effect

    Returns the new conversation ID so the frontend can update its state.
    """
    # Get parent entity and entity type before resetting
    parent_entity = conversation.get_parent_entity()
    parent_entity_type = conversation.parent_entity_type

    new_conversation = conversation_service.reset_conversation(conversation)

    # Update the parent entity's conversation reference
    if parent_entity_type == ParentEntityType.TASK:
        parent_entity.conversation_id = new_conversation.id  # type: ignore[union-attr]
    elif parent_entity_type == ParentEntityType.PROJECT:
        parent_entity.default_conversation_id = new_conversation.id  # type: ignore[union-attr]
    elif parent_entity_type == ParentEntityType.CODEBASE:
        parent_entity.default_conversation_id = new_conversation.id  # type: ignore[union-attr]

    return ResetConversationResponse(
        new_conversation_id=new_conversation.id,
        message="Conversation reset successfully.",
    )


@router.get("/{conversation_id}/todos", response_model=list[TodoItem])
async def get_conversation_todos(
    conversation: Conversation = Depends(get_verified_conversation),
) -> list[TodoItem]:
    """Get todo list for a Claude Code conversation.

    Returns the main session's todo list for Claude Code conversations.
    Returns empty list for non-Claude Code conversations or if no todos exist yet.
    """
    if conversation.engine != AgentEngine.CLAUDE_CODE:
        return []

    if not conversation.external_session_id:
        return []

    session_service = ClaudeCodeSessionService()
    try:
        return session_service.load_todo_list(conversation.external_session_id)
    except FileNotFoundError:
        return []


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
