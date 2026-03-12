"""Unified conversation API router."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.background_execution import run_agent_for_conversation
from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.engines import AgentEngine
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionService
from devboard.agents.events import ConversationEvent
from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution_manager import conversation_execution_manager
from devboard.api.dependencies.conversations import get_conversation_history_service
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.repositories import get_conversation_repository
from devboard.api.dependencies.services import (
    get_agent_config_service,
    get_conversation_service,
)
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    ToolApprovals,
)
from devboard.api.schemas.claude_code_todo import TodoItem
from devboard.api.schemas.common import ResetConversationResponse
from devboard.api.schemas.conversation import ConversationResponse
from devboard.api.schemas.integration import UpdateConversationModelRequest
from devboard.db.models import Conversation, ParentEntityType, Task, TaskStatus
from devboard.db.repositories import ConversationRepository
from devboard.services.conversation_service import ConversationService

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


def _start_agent_execution(conversation: Conversation, message_or_approvals: str | ToolApprovals) -> dict[str, int]:
    """Validate conversation state and start a background agent execution.

    Returns:
        dict with conversation_id

    Raises:
        HTTPException 400: If the conversation belongs to a completed task
        HTTPException 409: If an execution is already active for this conversation
    """
    conversation_parent = conversation.get_parent_entity()
    if isinstance(conversation_parent, Task) and conversation_parent.status == TaskStatus.COMPLETE:
        raise HTTPException(status_code=400, detail="Cannot send messages for completed tasks")

    cid = conversation.id
    try:
        conversation_execution_manager.start_execution(
            cid,
            lambda q, ie: run_agent_for_conversation(
                q, ie, conversation_id=cid, message_or_approvals=message_or_approvals
            ),
        )
    except ConversationBusyError as err:
        raise HTTPException(status_code=409, detail="An execution is already active for this conversation") from err

    return {"conversation_id": cid}


@router.post("/{conversation_id}/messages")
async def send_conversation_message(
    request: ChatRequest,
    conversation: Conversation = Depends(get_verified_conversation),
) -> dict[str, int]:
    """Send a message and start a background agent execution.

    Starts a background task for agent execution and returns immediately.
    Connect to GET /api/conversations/{conversation_id}/ws to receive events.

    Returns:
        {"conversation_id": <id>}

    Raises:
        HTTPException 409: If an execution is already active
    """
    return _start_agent_execution(conversation, request.message)


@router.post("/{conversation_id}/approve-tools")
async def approve_conversation_tools(
    request: ToolApprovals,
    conversation: Conversation = Depends(get_verified_conversation),
) -> dict[str, int]:
    """Submit tool approvals and resume background agent execution.

    Starts a background task to process tool approvals and continues agent execution.
    Connect to GET /api/conversations/{conversation_id}/ws to receive events.

    Returns:
        {"conversation_id": <id>}

    Raises:
        HTTPException 409: If an execution is already active
    """
    return _start_agent_execution(conversation, request)


@router.post("/{conversation_id}/interrupt")
async def interrupt_conversation(
    conversation: Conversation = Depends(get_verified_conversation),
) -> dict[str, str]:
    """Request graceful interruption of the active execution.

    Sets the interrupt flag on the active execution. The agent checks this flag
    periodically and stops gracefully, persisting messages received up to that point.

    Returns:
        {"status": "interrupt_requested"}

    Raises:
        HTTPException 404: If no active execution for this conversation
    """
    interrupted = conversation_execution_manager.request_interrupt(conversation.id)
    if not interrupted:
        raise HTTPException(status_code=404, detail="No active execution for this conversation")
    return {"status": "interrupt_requested"}


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
