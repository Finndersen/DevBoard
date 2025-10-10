"""Service for managing Claude Code conversation sessions.

This service reads Claude Code session history from JSONL files stored in
~/.claude/projects/<project-cwd>/<session_id>.jsonl and converts them to
DevBoard's ConversationMessage format.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from devboard.api.schemas.agent_conversation import ConversationMessage, MessageRole
from devboard.api.schemas.claude_code_todo import TodoItem

logger = logging.getLogger(__name__)


class ClaudeCodeSessionService:
    """Service for reading and parsing Claude Code session history.

    Searches for session files by ID across all project directories in
    ~/.claude/projects, eliminating the need to know the exact project path.
    """

    def __init__(self):
        """Initialize service.

        The service searches for session files across all project directories
        in ~/.claude/projects, eliminating the need to provide a project path.
        """
        self.claude_projects_dir = Path.home() / ".claude" / "projects"
        self.claude_todos_dir = Path.home() / ".claude" / "todos"

    def find_session_file(self, session_id: str) -> Path:
        """Find a session file by searching all project directories.

        Searches ~/.claude/projects/*/<session_id>.jsonl for the session file.
        This eliminates the need to know the exact project directory path.

        Args:
            session_id: The Claude Code session ID

        Returns:
            Path to the session JSONL file

        Raises:
            FileNotFoundError: If Claude projects directory doesn't exist or session file not found
        """
        if not self.claude_projects_dir.exists():
            raise FileNotFoundError(
                f"Claude Code projects directory not found: {self.claude_projects_dir}. "
                f"Ensure Claude Code has been run at least once."
            )

        # Search all project directories for the session file
        session_filename = f"{session_id}.jsonl"

        for project_dir in self.claude_projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            session_file = project_dir / session_filename
            if session_file.exists():
                logger.debug(f"Found session file: {session_file}")
                return session_file

        raise FileNotFoundError(f"Session file not found for ID: {session_id}. Searched in: {self.claude_projects_dir}")

    def get_last_session_message(self, session_id: str) -> ConversationMessage | None:
        """Get the last message from a Claude Code session.

        Reads the session JSONL file and returns the last non-empty line as a
        ConversationMessage. This is useful for parsing virtual tool call data
        from the most recent message.

        Args:
            session_id: The Claude Code session ID

        Returns:
            ConversationMessage containing the last message, or None if file is empty

        Raises:
            FileNotFoundError: If Claude projects directory or session file doesn't exist
            json.JSONDecodeError: If the last line of the JSONL file is malformed
            PermissionError: If unable to read the session file
        """
        # Find session file by searching all project directories
        session_file = self.find_session_file(session_id)

        with session_file.open("r") as f:
            content = f.read()

        # Split into lines and find last non-empty line
        lines = content.strip().split("\n")
        if not lines or not lines[-1].strip():
            return None

        # Parse the last line as JSON
        entry = json.loads(lines[-1])

        # Convert to ConversationMessage
        return self._parse_jsonl_entry(entry)

    def load_conversation_history(self, session_id: str) -> list[ConversationMessage]:
        """Load conversation history from a Claude Code session.

        Searches for the session file across all Claude Code project directories
        and converts user and assistant text messages to ConversationMessage objects.
        Filters out tool calls, summaries, and other non-conversational message types.

        Args:
            session_id: The Claude Code session ID

        Returns:
            List of ConversationMessage objects in chronological order

        Raises:
            FileNotFoundError: If Claude projects directory or session file doesn't exist
            json.JSONDecodeError: If the JSONL file is malformed
            PermissionError: If unable to read the session file
        """
        # Find session file by searching all project directories (raises FileNotFoundError if not found)
        session_file = self.find_session_file(session_id)

        messages: list[ConversationMessage] = []

        try:
            with session_file.open("r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)
                        message = self._parse_jsonl_entry(entry)
                        if message:
                            messages.append(message)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping malformed JSONL entry at line {line_num}: {e}")
                        continue
        except PermissionError as e:
            raise PermissionError(f"Permission denied reading session file: {session_file}") from e

        return messages

    def _parse_jsonl_entry(self, entry: dict) -> ConversationMessage | None:
        """Parse a single JSONL entry into a ConversationMessage.

        Args:
            entry: Dictionary parsed from a JSONL line

        Returns:
            ConversationMessage if the entry is a user or assistant text message,
            None if the entry should be filtered out (summaries, tool calls, etc.)
        """
        msg_type = entry["type"]

        # Filter out summaries and other message types early
        if msg_type not in ("user", "assistant"):
            return None

        # Parse timestamp
        timestamp = datetime.fromisoformat(entry["timestamp"])

        # Parse user messages
        if msg_type == "user":
            message_data = entry.get("message", {})
            content = message_data.get("content")

            # Skip tool result messages (content is array with tool_result)
            if isinstance(content, list):
                return None

            return ConversationMessage(
                id=0,  # JSONL doesn't have sequential IDs, could use hash of uuid
                role=MessageRole.USER,
                text_content=content or "",
                timestamp=timestamp,
            )

        # Parse assistant messages
        elif msg_type == "assistant":
            message_data = entry.get("message", {})
            content = message_data.get("content", [])

            # Extract only text content blocks
            text_parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))

            # Skip if no text content (only tool calls)
            if not text_parts:
                return None

            return ConversationMessage(
                id=0,
                role=MessageRole.AGENT,
                text_content="\n".join(text_parts),
                timestamp=timestamp,
            )

        # Filter out summaries and other message types
        return None

    def find_main_session_todo_file(self, session_id: str) -> Path:
        """Find the main session's todo file.

        Looks for the self-referencing todo file pattern:
        <session_id>-agent-<session_id>.json

        Args:
            session_id: The Claude Code session ID

        Returns:
            Path to the main session's todo file

        Raises:
            FileNotFoundError: If todos directory or todo file doesn't exist
        """
        if not self.claude_todos_dir.exists():
            raise FileNotFoundError(
                f"Claude Code todos directory not found: {self.claude_todos_dir}. "
                f"Ensure Claude Code has been run at least once."
            )

        # Main session todos use self-referencing pattern: session_id-agent-session_id
        todo_filename = f"{session_id}-agent-{session_id}.json"
        todo_file = self.claude_todos_dir / todo_filename

        if not todo_file.exists():
            raise FileNotFoundError(
                f"Main session todo file not found: {todo_filename}. The session may not have created any todos yet."
            )

        return todo_file

    def find_all_session_todo_files(self, session_id: str) -> list[Path]:
        """Find all todo files for a session (main session + sub-agents).

        Looks for todo files matching the pattern:
        <session_id>-agent-*.json

        This includes:
        - Main session: <session_id>-agent-<session_id>.json
        - Sub-agents: <session_id>-agent-<other_uuid>.json

        Args:
            session_id: The Claude Code session ID

        Returns:
            List of paths to todo files, sorted by filename. Empty list if none found.
        """
        if not self.claude_todos_dir.exists():
            return []

        pattern = f"{session_id}-agent-*.json"
        return sorted(self.claude_todos_dir.glob(pattern))

    def load_todo_list(self, session_id: str, include_subagents: bool = False) -> list[TodoItem]:
        """Load todo list for a Claude Code session.

        Loads the main session's todo list, and optionally includes todos from
        any sub-agent sessions spawned via the Task tool.

        Args:
            session_id: The Claude Code session ID
            include_subagents: If True, include todos from sub-agent sessions

        Returns:
            List of TodoItem objects. Returns empty list if no todo files exist
            or if files are empty.

        Raises:
            json.JSONDecodeError: If a todo file contains invalid JSON
        """
        if include_subagents:
            # Get all todo files (main + sub-agents)
            todo_files = self.find_all_session_todo_files(session_id)
        else:
            # Get just the main session todo file
            try:
                main_todo_file = self.find_main_session_todo_file(session_id)
                todo_files = [main_todo_file]
            except FileNotFoundError:
                # No todo file exists yet - return empty list
                return []

        # Load and parse all todo files
        all_todos: list[TodoItem] = []

        for todo_file in todo_files:
            try:
                with todo_file.open("r") as f:
                    content = f.read().strip()

                    # Handle empty files
                    if not content or content == "[]":
                        continue

                    # Parse JSON array
                    todos_data = json.loads(content)

                    # Convert to TodoItem objects
                    for todo_data in todos_data:
                        # Handle snake_case conversion for activeForm field
                        if "activeForm" in todo_data:
                            todo_data["active_form"] = todo_data.pop("activeForm")

                        todo_item = TodoItem(**todo_data)
                        all_todos.append(todo_item)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse todo file {todo_file}: {e}")
                raise

        return all_todos
