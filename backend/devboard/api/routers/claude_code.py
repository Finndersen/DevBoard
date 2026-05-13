"""Claude Code session viewer API endpoints."""

import logfire
from fastapi import APIRouter, Depends, HTTPException, Query

from devboard.agents.engines.claude_code.session.manager import ClaudeSessionManager
from devboard.agents.events import ConversationEvent
from devboard.api.dependencies.repositories import get_claude_project_cache_repository, get_conversation_repository
from devboard.api.schemas.claude_code import (
    ClaudeCodeProjectResponse,
    ClaudeCodeSessionResponse,
    McpServerResponse,
    McpServerStatus,
    McpServerType,
    SessionLocateResponse,
    SessionSearchResultResponse,
    SessionTaskInfoResponse,
    SubAgentInfoResponse,
)
from devboard.db.repositories.claude_project import ClaudeProjectCacheRepository
from devboard.db.repositories.conversation import ConversationRepository
from devboard.integrations.shell import ShellCommandError, execute_shell_command

router = APIRouter()


def _parse_mcp_servers(output: str) -> list[McpServerResponse]:
    """Parse `claude mcp list` output into structured server data.

    Args:
        output: Raw output from `claude mcp list` command

    Returns:
        List of parsed MCP server responses

    Raises:
        ValueError: If output format is invalid
    """
    servers: list[McpServerResponse] = []

    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Split on first ": " to get name and remainder
        if ": " not in line:
            continue

        name, remainder = line.split(": ", 1)

        # Split on last " - " to get url_or_command and status
        if " - " not in remainder:
            continue

        # Find the last occurrence of " - "
        last_dash_idx = remainder.rfind(" - ")
        url_or_command = remainder[:last_dash_idx]
        status_text = remainder[last_dash_idx + 3 :]  # Skip " - "

        # Map status text to enum
        if "Connected" in status_text:
            status = McpServerStatus.connected
        elif "Needs authentication" in status_text:
            status = McpServerStatus.needs_auth
        elif "Failed" in status_text:
            status = McpServerStatus.failed
        else:
            logfire.warning("Unknown MCP server status in output", status_text=status_text, line=line)
            continue

        # Detect type: remote if URL, local if command
        server_type = (
            McpServerType.remote
            if url_or_command.startswith("http://") or url_or_command.startswith("https://")
            else McpServerType.local
        )

        servers.append(
            McpServerResponse(
                name=name,
                url_or_command=url_or_command,
                status=status,
                type=server_type,
            )
        )

    return servers


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

    results: list[ClaudeCodeSessionResponse] = []
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


@router.get("/mcp-servers", response_model=list[McpServerResponse])
async def get_mcp_servers() -> list[McpServerResponse]:
    """Get status of configured MCP servers.

    Executes `claude mcp list` command and parses the output to return
    structured MCP server status information.

    Returns:
        List of MCP server status responses

    Raises:
        HTTPException: 502 if claude CLI is not found or command fails
    """
    try:
        result = await execute_shell_command(["claude", "mcp", "list"], raise_on_error=False)
    except ShellCommandError as e:
        raise HTTPException(status_code=502, detail=f"Failed to list MCP servers: {str(e)}") from e

    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to list MCP servers: {result.stderr or 'Unknown error'}",
        )

    return _parse_mcp_servers(result.stdout)
