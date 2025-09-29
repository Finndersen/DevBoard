"""Unified conversation API router."""

from fastapi import APIRouter, Depends

from devboard.api.dependencies.agents import get_conversation_agent
from devboard.api.dependencies.repositories import get_conversation_repository
from devboard.api.schemas.agent_conversation import (
    ChatRequest,
    ConversationMessage,
    MessageRole,
    PromptResponse,
    ToolApprovalRequest,
)
from devboard.api.schemas.common import DeleteResponse
from devboard.db.models.messages import MessageType
from devboard.db.repositories.conversation import ConversationRepository
from devboard.services.agent_conversation import AgentConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessage])
def get_conversation_messages(
    conversation_id: int,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> list[ConversationMessage]:
    """Get all messages for a conversation."""

    messages = conversation_repo.get_messages(conversation_id=conversation_id, exclude_tool_calls=True)

    return [
        ConversationMessage(
            id=msg.id,
            role=MessageRole.USER if msg.message_type == MessageType.USER_PROMPT else MessageRole.AGENT,
            text_content=msg.text_content,
            timestamp=msg.timestamp,
        )
        for msg in messages
    ]


@router.post("/{conversation_id}/messages", response_model=PromptResponse)
async def send_conversation_message(
    conversation_id: int,
    request: ChatRequest,
    agent=Depends(get_conversation_agent),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> PromptResponse:
    """Send message to any conversation."""
    # Create service manually with the resolved dependencies
    conversation_service = AgentConversationService(
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
    conversation_service = AgentConversationService(
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
