"""Claude Code session viewer API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from devboard.agents.engines.claude_code.session.manager import ClaudeSessionManager
from devboard.agents.events import ConversationEvent
from devboard.api.schemas.claude_code import (
    ClaudeCodeProjectResponse,
    ClaudeCodeSessionResponse,
    SessionSearchResultResponse,
)

router = APIRouter()


def _get_manager() -> ClaudeSessionManager:
    return ClaudeSessionManager()


@router.get("/projects", response_model=list[ClaudeCodeProjectResponse])
async def list_projects() -> list[ClaudeCodeProjectResponse]:
    """List all Claude Code projects with metadata, ordered by last activity."""
    manager = _get_manager()
    projects = manager.list_projects()
    return [ClaudeCodeProjectResponse.model_validate(p.__dict__) for p in projects]


@router.get("/projects/{encoded_project_path}/sessions", response_model=list[ClaudeCodeSessionResponse])
async def list_sessions(encoded_project_path: str) -> list[ClaudeCodeSessionResponse]:
    """List sessions for a Claude Code project, ordered by last activity."""
    manager = _get_manager()
    try:
        sessions = await manager.list_sessions(encoded_project_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [ClaudeCodeSessionResponse.model_validate(s.__dict__) for s in sessions]


@router.get("/sessions/{session_id}/messages", response_model=list[ConversationEvent])
async def get_session_messages(session_id: str) -> list[ConversationEvent]:
    """Get full conversation event history for a session."""
    manager = _get_manager()
    try:
        return await manager.get_session_messages(session_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/sessions/search", response_model=list[SessionSearchResultResponse])
async def search_sessions(
    query: str = Query(..., description="Search pattern"),
    project_path: str | None = Query(None, description="Optional project filesystem path to scope search"),
) -> list[SessionSearchResultResponse]:
    """Search session JSONL files using ripgrep."""
    manager = _get_manager()
    results = await manager.search_sessions(query, project_path)
    return [SessionSearchResultResponse.model_validate(r.__dict__) for r in results]
