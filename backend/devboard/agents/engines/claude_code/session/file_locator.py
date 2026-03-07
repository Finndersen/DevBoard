"""File location utilities for Claude Code session and todo files."""

from pathlib import Path

import logfire


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
