"""Background agent runs API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.repositories import (
    get_background_agent_run_repository,
    get_conversation_repository,
)
from devboard.api.schemas.background_agent import BackgroundAgentRunResponse
from devboard.api.schemas.conversation import ConversationResponse
from devboard.db.repositories.background_agent import BackgroundAgentRunRepository
from devboard.db.repositories.conversation import ConversationRepository

router = APIRouter()


@router.get("/{run_id}", response_model=BackgroundAgentRunResponse)
async def get_background_agent_run(
    run_id: int,
    repo: BackgroundAgentRunRepository = Depends(get_background_agent_run_repository),
) -> BackgroundAgentRunResponse:
    """Get background agent run details."""
    run = repo.get_by_id(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Background agent run not found")
    return BackgroundAgentRunResponse.model_validate(run)


@router.get("/{run_id}/conversation", response_model=ConversationResponse)
async def get_background_agent_run_conversation(
    run_id: int,
    run_repo: BackgroundAgentRunRepository = Depends(get_background_agent_run_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationResponse:
    """Get the conversation transcript for a background agent run."""
    run = run_repo.get_by_id(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Background agent run not found")
    conversation = conversation_repo.get_by_id(run.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse.model_validate(conversation)
