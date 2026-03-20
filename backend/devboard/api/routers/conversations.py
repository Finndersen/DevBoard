"""Unified conversation API router."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.engines import AgentEngine
from devboard.agents.engines.claude_code.session import ClaudeCodeSessionService
from devboard.agents.events import ConversationEvent
from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution.registry import get_execution_manager
from devboard.api.dependencies.conversations import get_conversation_history_service
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.factories import create_agent_role_for_conversation
from devboard.api.dependencies.repositories import get_conversation_repository
from devboard.api.dependencies.services import (
    ExecutionServices,
    get_agent_config_service,
    get_conversation_service,
    get_execution_services,
)
from devboard.api.schemas.agent_config import AgentConfigResponse, ToolInfo
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    ToolApprovals,
)
from devboard.api.schemas.claude_code_todo import TodoItem
from devboard.api.schemas.common import DeleteResponse, ResetConversationResponse
from devboard.api.schemas.conversation import ConversationResponse, ConversationUpdate
from devboard.api.schemas.integration import UpdateConversationModelRequest
from devboard.db.models import Conversation, ParentEntityType, Project, Task, TaskStatus
from devboard.db.repositories import ConversationRepository
from devboard.services.conversation_service import ConversationService
from devboard.services.project_directory import ensure_project_directory

router = APIRouter()


@router.get("/", response_model=list[ConversationResponse])
async def list_conversations(
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> list[ConversationResponse]:
    """List all top-level, non-archived conversations ordered by recent activity."""
    rows = conversation_repo.get_all_top_level()
    return [
        ConversationResponse(
            id=row["conversation"].id,
            parent_entity_type=row["conversation"].parent_entity_type,
            parent_entity_id=row["conversation"].parent_entity_id,
            agent_role=row["conversation"].agent_role,
            engine=row["conversation"].engine,
            model_id=row["conversation"].model_id,
            is_active=row["conversation"].is_active,
            external_session_id=row["conversation"].external_session_id,
            title=row["conversation"].title,
            last_activity_at=row["conversation"].last_activity_at,
            created_at=row["conversation"].created_at,
            parent_entity_name=row["parent_entity_name"],
            project_name=row["project_name"],
        )
        for row in rows
    ]


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
        title=conversation.title,
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


def _start_agent_execution(
    conversation: Conversation,
    message_or_approvals: str | ToolApprovals,
    conversation_repo: ConversationRepository,
) -> dict[str, int]:
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

    # Touch last_activity_at now so the conversation list is correctly ordered
    # as soon as this request completes, before the background task starts.
    conversation_repo.update_last_activity(conversation)

    cid = conversation.id
    try:
        get_execution_manager().start_agent_execution(cid, message_or_approvals)
    except ConversationBusyError as err:
        raise HTTPException(status_code=409, detail="An execution is already active for this conversation") from err

    return {"conversation_id": cid}


@router.post("/{conversation_id}/messages")
async def send_conversation_message(
    request: ChatRequest,
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict[str, int]:
    """Send a message and start a background agent execution."""
    # Auto-set title from first user message
    conversation_service.set_conversation_title_from_message(conversation, request.message)
    return _start_agent_execution(conversation, request.message, conversation_repo)


@router.post("/{conversation_id}/approve-tools")
async def approve_conversation_tools(
    request: ToolApprovals,
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> dict[str, int]:
    """Submit tool approvals and resume background agent execution.

    Starts a background task to process tool approvals and continues agent execution.
    Connect to GET /api/conversations/{conversation_id}/ws to receive events.

    Returns:
        {"conversation_id": <id>}

    Raises:
        HTTPException 409: If an execution is already active
    """
    return _start_agent_execution(conversation, request, conversation_repo)


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
    interrupted = get_execution_manager().request_interrupt(conversation.id)
    if not interrupted:
        raise HTTPException(status_code=404, detail="No active execution for this conversation")
    return {"status": "interrupt_requested"}


@router.post("/{conversation_id}/reset", response_model=ResetConversationResponse)
async def reset_conversation(
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ResetConversationResponse:
    """Reset a conversation by deleting it and creating a new one."""
    parent_entity = conversation.get_parent_entity()
    parent_entity_type = conversation.parent_entity_type

    new_conversation = conversation_service.reset_conversation(conversation)

    # Update the parent entity's conversation reference (tasks only)
    if parent_entity_type == ParentEntityType.TASK:
        parent_entity.conversation_id = new_conversation.id  # type: ignore[union-attr]

    return ResetConversationResponse(
        new_conversation_id=new_conversation.id,
        message="Conversation reset successfully.",
    )


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    request: ConversationUpdate,
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationResponse:
    """Update conversation properties (e.g., title)."""
    conversation_repo.update_title(conversation, request.title)
    return ConversationResponse.model_validate(conversation)


@router.delete("/{conversation_id}", response_model=DeleteResponse)
async def delete_conversation(
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> DeleteResponse:
    """Delete a specific conversation."""
    conversation_repo.delete_by_id(conversation.id)
    return DeleteResponse(message="Conversation deleted successfully")


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


@router.get("/{conversation_id}/agent-config", response_model=AgentConfigResponse)
async def get_agent_config(
    conversation: Conversation = Depends(get_verified_conversation),
    exec_services: ExecutionServices = Depends(get_execution_services),
) -> AgentConfigResponse:
    """Get the full assembled agent configuration for a conversation."""
    parent = conversation.get_parent_entity()
    # Working dir should not matter or be used since the role is not actually used for execution here
    if isinstance(parent, Task):
        working_dir = parent.codebase.local_path
    elif isinstance(parent, Project):
        working_dir = str(ensure_project_directory(parent))
    else:
        working_dir = parent.local_path

    role = await create_agent_role_for_conversation(
        conversation=conversation,
        document_repo=exec_services.document_repo,
        agent_config_service=exec_services.agent_config_service,
        integration_service=exec_services.integration_service,
        task_service=exec_services.task_service,
        task_git_service=exec_services.task_git_service,
        conversation_repo=exec_services.conversation_repo,
        working_dir=working_dir,
    )

    agent_config = exec_services.agent_config_service.get_agent_configuration(conversation.agent_role)

    role_tools = [
        ToolInfo(
            name=tool.name,
            description=tool.description,
            input_schema=tool.function_schema.json_schema,
            source="role",
        )
        for tool in role.get_tools()
    ]

    mcp_tools = [
        ToolInfo(
            name=mcp_tool.name,
            description=mcp_tool.description,
            input_schema=mcp_tool.input_schema,
            source="mcp",
            server_name=mcp_tool.server.name,
        )
        for mcp_tool in exec_services.agent_config_service.get_enabled_mcp_tools(conversation.agent_role)
    ]

    builtin_tools = [ToolInfo(name=name, source="builtin") for name in role.allowed_builtin_tools]

    return AgentConfigResponse(
        agent_role=conversation.agent_role.value,
        behaviour_guidelines=role.get_system_prompt(),
        context_content=await role.get_context_content(),
        custom_instructions=agent_config.custom_instructions,
        role_tools=role_tools,
        mcp_tools=mcp_tools,
        builtin_tools=builtin_tools,
    )
