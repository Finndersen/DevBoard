"""Service for managing Claude Code conversation sessions.

This service reads Claude Code session history from JSONL files stored in
~/.claude/projects/<project-cwd>/<session_id>.jsonl and provides low-level
access to session messages and todos.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import logfire

from devboard.api.schemas.claude_code_todo import TodoItem


@dataclass
class TextBlock:
    """Structure of a text content block in assistant messages.

    This represents plain text content in Claude's response.
    """

    type: str  # Always "text"
    text: str  # The text content


@dataclass
class ToolUseBlock:
    """Structure of a tool_use block in assistant messages.

    This represents Claude's request to call a tool with specific arguments.
    """

    type: str  # Always "tool_use"
    id: str  # Tool call ID (e.g., "toolu_0121WU3WtkV7WG4CNpPkqR7d")
    name: str  # Tool name (e.g., "Bash", "Read", "Write")
    input: dict[str, Any]  # Tool arguments/parameters


@dataclass
class ToolResultBlock:
    """Structure of a tool_result block in user messages.

    This represents the result of a tool execution being returned to Claude.
    """

    type: str  # Always "tool_result"
    tool_use_id: str  # Corresponding tool call ID
    content: str | list[dict[str, Any]]  # Tool result content
    is_error: bool  # Whether the tool execution failed


# Union type for all possible content blocks
ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock


class SessionMessageRole(StrEnum):
    """Roles for session messages."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class SessionMessage:
    """Complete message data from Claude Code session JSONL file.

    This dataclass captures all relevant data from a session message,
    including tool calls and results that may be filtered out of
    conversation history but are useful for debugging and processing.

    Content can be:
    - str: For user messages (plain text)
    - list[ContentBlock]: For assistant messages (list of text/tool blocks)
    - list[ToolResultBlock]: For user messages with tool results
    """

    uuid: str
    timestamp: datetime
    role: SessionMessageRole
    content: str | list[ContentBlock]
    tool_calls: list[ToolUseBlock] | None  # Tool use blocks if present
    tool_results: list[ToolResultBlock] | None  # Tool result blocks if present
    line_num: int  # Line number in the JSONL file (1-indexed)

    @property
    def text_content(self) -> str:
        """Extract text content from the message.

        For user messages, content is already a string.
        For assistant messages, content is a list of blocks - extract text blocks.

        Returns:
            Extracted text content, or empty string if no text content
        """
        if isinstance(self.content, str):
            # User message - content is already a string
            return self.content or ""
        elif isinstance(self.content, list):
            # Assistant message or tool result - extract text blocks
            text_parts = []
            for block in self.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
            return "\n".join(text_parts)
        else:
            return ""


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

        # Use rglob to search for the session file (max depth 2: projects/*/session.jsonl)
        session_filename = f"{session_id}.jsonl"
        pattern = f"*/{session_filename}"

        for session_file in self.claude_projects_dir.glob(pattern):
            if session_file.is_file():
                logfire.debug(f"Found session file: {session_file}")
                return session_file

        raise FileNotFoundError(f"Session file not found for ID: {session_id}. Searched in: {self.claude_projects_dir}")

    def get_last_session_message(self, session_id: str) -> SessionMessage | None:
        """Get the last message from a Claude Code session.

        Reads the session JSONL file and returns the last non-empty line as a
        SessionMessage with complete data. This is useful for parsing virtual
        tool call data from the most recent message.

        Args:
            session_id: The Claude Code session ID

        Returns:
            SessionMessage containing the last message, or None if file is empty

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

        # Convert to SessionMessage with line_num as the last line number
        return self._parse_session_message(entry, line_num=len(lines))

    def load_session_messages(self, session_id: str) -> list[SessionMessage]:
        """Load complete session messages from a Claude Code session.

        This is a low-level method that returns full SessionMessage objects
        including tool calls, tool results, and all metadata.

        Args:
            session_id: The Claude Code session ID

        Returns:
            List of SessionMessage objects in chronological order

        Raises:
            FileNotFoundError: If Claude projects directory or session file doesn't exist
            json.JSONDecodeError: If the JSONL file is malformed
            PermissionError: If unable to read the session file
        """
        session_file = self.find_session_file(session_id)
        messages: list[SessionMessage] = []
        with session_file.open("r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    message = self._parse_session_message(entry, line_num=line_num)
                    if message:
                        messages.append(message)
                except json.JSONDecodeError as e:
                    logfire.warning(f"Skipping malformed JSONL entry at line {line_num}: {e}")
                    continue

        return messages

    @staticmethod
    def _parse_content_block(block_dict: dict[str, Any]) -> ContentBlock:
        """Parse a content block dict into the appropriate dataclass.

        Args:
            block_dict: Dictionary representing a content block

        Returns:
            ContentBlock instance (TextBlock, ToolUseBlock, or ToolResultBlock)
        """
        block_type = block_dict.get("type")

        if block_type == "text":
            return TextBlock(
                type=block_dict["type"],
                text=block_dict["text"],
            )
        elif block_type == "tool_use":
            return ToolUseBlock(
                type=block_dict["type"],
                id=block_dict["id"],
                name=block_dict["name"],
                input=block_dict["input"],
            )
        elif block_type == "tool_result":
            return ToolResultBlock(
                type=block_dict["type"],
                tool_use_id=block_dict["tool_use_id"],
                content=block_dict["content"],
                is_error=block_dict.get("is_error", False),
            )
        else:
            # Unknown block type - raise error or return a generic block
            raise ValueError(f"Unknown content block type: {block_type}")

    def _parse_session_message(self, entry: dict[str, Any], line_num: int) -> SessionMessage | None:
        """Parse a JSONL entry into a SessionMessage with full data.

        Args:
            entry: Dictionary parsed from a JSONL line
            line_num: Line number in the JSONL file (1-indexed)

        Returns:
            SessionMessage with complete data, or None if not a message type
        """
        msg_type = entry.get("type")

        # Only parse user and assistant messages
        if msg_type not in ("user", "assistant"):
            return None

        uuid = entry.get("uuid", "")
        timestamp = datetime.fromisoformat(entry["timestamp"])
        message_data = entry.get("message", {})

        if msg_type == "user":
            content = message_data.get("content")
            # Check if it's a tool result (array format)
            tool_results = None
            parsed_content: str | list[ContentBlock] = content

            if isinstance(content, list):
                # Parse all tool result blocks
                tool_results_raw = [
                    item for item in content if isinstance(item, dict) and item.get("type") == "tool_result"
                ]
                if tool_results_raw:
                    # Convert to dataclass instances
                    tool_results = [cast(ToolResultBlock, self._parse_content_block(item)) for item in tool_results_raw]
                    # Assign as list[ContentBlock] (ToolResultBlock is a ContentBlock)
                    parsed_content = cast(list[ContentBlock], tool_results)
                else:
                    parsed_content = ""

            return SessionMessage(
                uuid=uuid,
                timestamp=timestamp,
                role=SessionMessageRole.USER,
                content=parsed_content,
                tool_calls=None,
                tool_results=tool_results,
                line_num=line_num,
            )

        elif msg_type == "assistant":
            content_raw = message_data.get("content", [])

            # Parse all content blocks and extract tool calls
            parsed_blocks: list[ContentBlock] = []
            tool_calls: list[ToolUseBlock] | None = None

            if isinstance(content_raw, list):
                # Parse all content blocks into dataclass instances
                for block_dict in content_raw:
                    if isinstance(block_dict, dict):
                        parsed_blocks.append(self._parse_content_block(block_dict))

                # Extract tool calls from parsed blocks
                tool_calls_list = [block for block in parsed_blocks if isinstance(block, ToolUseBlock)]
                tool_calls = tool_calls_list if tool_calls_list else None

            return SessionMessage(
                uuid=uuid,
                timestamp=timestamp,
                role=SessionMessageRole.ASSISTANT,
                content=parsed_blocks,
                tool_calls=tool_calls,
                tool_results=None,
                line_num=line_num,
            )

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
                logfire.error(f"Failed to parse todo file {todo_file}: {e}")
                raise

        return all_todos
