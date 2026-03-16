"""Claude Code session viewer API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from devboard.agents.engines.claude_code.session.manager import ClaudeSessionManager
from devboard.agents.events import ConversationEvent
from devboard.api.dependencies.repositories import get_claude_project_cache_repository, get_conversation_repository
from devboard.api.schemas.claude_code import (
    ClaudeCodeProjectResponse,
    ClaudeCodeSessionResponse,
    SessionLocateResponse,
    SessionSearchResultResponse,
    SessionTaskInfoResponse,
    SubAgentInfoResponse,
)
from devboard.db.repositories.claude_project import ClaudeProjectCacheRepository
from devboard.db.repositories.conversation import ConversationRepository

router = APIRouter()


def _get_manager(
    cache_repo: ClaudeProjectCacheRepository = Depends(get_claude_project_cache_repository),
) -> ClaudeSessionManager:
    return ClaudeSessionManager(project_cache=cache_repo)


@router.get("/projects", response_model=list[ClaudeCodeProjectResponse])
async def list_projects(
    manager: ClaudeSessionManager = Depends(_get_manager),
) -> list[ClaudeCodeProjectResponse]:
    """List all Claude Code projects with metadata, ordered by last activity."""
    projects = manager.list_projects()
    return [ClaudeCodeProjectResponse.model_validate(p.__dict__) for p in projects]


@router.get("/projects/{encoded_project_path}/sessions", response_model=list[ClaudeCodeSessionResponse])
async def list_sessions(
    encoded_project_path: str,
    manager: ClaudeSessionManager = Depends(_get_manager),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> list[ClaudeCodeSessionResponse]:
    """List sessions for a Claude Code project, ordered by last activity."""
    try:
        sessions = await manager.list_sessions(encoded_project_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    session_ids = {s.session_id for s in sessions}
    task_info_by_session = conversation_repo.get_task_info_by_session_ids(session_ids)
    sub_agent_info_by_session = conversation_repo.get_sub_agent_info_by_session_ids(session_ids)

    results = []
    for s in sessions:
        task_info_data = task_info_by_session.get(s.session_id)
        task_info = (
            SessionTaskInfoResponse(
                task_id=task_info_data["task_id"],
                task_title=task_info_data["task_title"],
                agent_role=task_info_data["agent_role"],
            )
            if task_info_data
            else None
        )
        sub_agent_data = sub_agent_info_by_session.get(s.session_id)
        sub_agent_info = (
            SubAgentInfoResponse(
                agent_role=sub_agent_data["agent_role"],
                parent_task_id=sub_agent_data["parent_task_id"],
                parent_task_title=sub_agent_data["parent_task_title"],
            )
            if sub_agent_data
            else None
        )
        results.append(ClaudeCodeSessionResponse(**s.__dict__, task_info=task_info, sub_agent_info=sub_agent_info))
    return results


@router.get("/sessions/{session_id}/locate", response_model=SessionLocateResponse)
async def locate_session(
    session_id: str,
    manager: ClaudeSessionManager = Depends(_get_manager),
) -> SessionLocateResponse:
    """Locate a session's project by session ID."""
    try:
        project_encoded_path = manager.locate_session(session_id)
        return SessionLocateResponse(project_encoded_path=project_encoded_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/sessions/{session_id}/messages", response_model=list[ConversationEvent])
async def get_session_messages(
    session_id: str,
    manager: ClaudeSessionManager = Depends(_get_manager),
) -> list[ConversationEvent]:
    """Get full conversation event history for a session."""
    try:
        return await manager.get_session_messages(session_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/sessions/{session_id}/subagents/{agent_id}/messages", response_model=list[ConversationEvent])
async def get_sub_agent_messages(
    session_id: str,
    agent_id: str,
    manager: ClaudeSessionManager = Depends(_get_manager),
) -> list[ConversationEvent]:
    """Get full conversation event history for a sub-agent of a session."""
    try:
        return await manager.get_sub_agent_messages(session_id, agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/sessions/search", response_model=list[SessionSearchResultResponse])
async def search_sessions(
    query: str = Query(..., description="Search pattern"),
    project_path: str | None = Query(None, description="Optional project filesystem path to scope search"),
    manager: ClaudeSessionManager = Depends(_get_manager),
) -> list[SessionSearchResultResponse]:
    """Search session JSONL files using ripgrep."""
    results = await manager.search_sessions(query, project_path)
    return [SessionSearchResultResponse.model_validate(r.__dict__) for r in results]
