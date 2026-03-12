"""File location utilities for Claude Code session and todo files."""

import re
from pathlib import Path

import logfire

_AGENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-]+$")


def find_session_file(session_id: str, claude_projects_dir: Path) -> Path:
    """Find a session file by searching all project directories.

    Searches <claude_projects_dir>/*/<session_id>.jsonl for the session file.

    Raises:
        FileNotFoundError: If projects directory doesn't exist or session file not found
    """
    if not claude_projects_dir.exists():
        raise FileNotFoundError(
            f"Claude Code projects directory not found: {claude_projects_dir}. "
            f"Ensure Claude Code has been run at least once."
        )

    session_filename = f"{session_id}.jsonl"
    pattern = f"*/{session_filename}"

    for session_file in claude_projects_dir.glob(pattern):
        if session_file.is_file():
            logfire.debug(f"Found session file: {session_file}")
            return session_file

    raise FileNotFoundError(f"Session file not found for ID: {session_id}. Searched in: {claude_projects_dir}")


def find_main_session_todo_file(session_id: str, claude_todos_dir: Path) -> Path:
    """Find the main session's todo file using the self-referencing pattern.

    Looks for: <session_id>-agent-<session_id>.json

    Raises:
        FileNotFoundError: If todos directory or todo file doesn't exist
    """
    if not claude_todos_dir.exists():
        raise FileNotFoundError(
            f"Claude Code todos directory not found: {claude_todos_dir}. Ensure Claude Code has been run at least once."
        )

    todo_filename = f"{session_id}-agent-{session_id}.json"
    todo_file = claude_todos_dir / todo_filename

    if not todo_file.exists():
        raise FileNotFoundError(
            f"Main session todo file not found: {todo_filename}. The session may not have created any todos yet."
        )

    return todo_file


def find_sub_agent_session_file(parent_session_id: str, agent_id: str, claude_projects_dir: Path) -> Path:
    """Find a sub-agent session file given the parent session ID and agent ID.

    Sub-agent files are located at: <parent_session_dir>/<parent_session_id>/subagents/agent-<agent_id>.jsonl

    Raises:
        ValueError: If agent_id contains invalid characters (path traversal prevention)
        FileNotFoundError: If the sub-agent session file does not exist
    """
    if not _AGENT_ID_PATTERN.match(agent_id):
        raise ValueError(f"Invalid agent_id: {agent_id}")

    parent_file = find_session_file(parent_session_id, claude_projects_dir)
    sub_agent_file = parent_file.parent / parent_session_id / "subagents" / f"agent-{agent_id}.jsonl"

    if not sub_agent_file.is_file():
        raise FileNotFoundError(
            f"Sub-agent session file not found: agent-{agent_id}.jsonl for session {parent_session_id}"
        )

    logfire.debug(f"Found sub-agent session file: {sub_agent_file}")
    return sub_agent_file


def find_all_session_todo_files(session_id: str, claude_todos_dir: Path) -> list[Path]:
    """Find all todo files for a session (main session + sub-agents).

    Looks for todo files matching: <session_id>-agent-*.json

    Returns:
        List of paths sorted by filename. Empty list if none found or dir doesn't exist.
    """
    if not claude_todos_dir.exists():
        return []

    pattern = f"{session_id}-agent-*.json"
    return sorted(claude_todos_dir.glob(pattern))
