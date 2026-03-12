from fastapi import Depends

from devboard.agents.conversation_history import ConversationHistoryService
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.factories import create_conversation_history_service
from devboard.api.dependencies.repositories import get_conversation_repository
from devboard.db.models import Conversation
from devboard.db.repositories import ConversationRepository


def get_conversation_history_service(
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationHistoryService:
    """Get conversation history service instance.

    FastAPI dependency that creates the appropriate history service (PydanticAI or Claude Code)
    based on the conversation's engine configuration. Does not require agent role.

    Args:
        conversation: Verified conversation instance
        conversation_repo: Conversation repository

    Returns:
        ConversationHistoryService instance (PydanticAI or Claude Code implementation)

    Raises:
        HTTPException: 400 if unsupported engine
    """
    return create_conversation_history_service(
        conversation=conversation,
        conversation_repo=conversation_repo,
    )
