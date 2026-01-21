"""Service for managing Claude Code conversation sessions.

This service reads Claude Code session history from JSONL files stored in
~/.claude/projects/<project-cwd>/<session_id>.jsonl and provides low-level
access to session messages and todos.
"""

import json
import platform
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

import logfire

from devboard.api.schemas.claude_code_todo import TodoItem
from devboard.integrations.shell import execute_shell_command


# TypedDict structures for JSONL entry types
class CacheCreationDict(TypedDict):
    """Cache creation statistics in usage data."""

    ephemeral_5m_input_tokens: int
    ephemeral_1h_input_tokens: int


class UsageDict(TypedDict):
    """Token usage statistics in API response.

    Core fields (input_tokens, output_tokens) are always present.
    Caching-related fields are present when prompt caching is used.
    """

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: NotRequired[int]
    cache_read_input_tokens: NotRequired[int]
    cache_creation: NotRequired[CacheCreationDict]
    service_tier: NotRequired[str]


class TextBlockDict(TypedDict):
    """Text content block in a message."""

    type: str  # "text"
    text: str


class ToolUseBlockDict(TypedDict):
    """Tool use content block in assistant messages."""

    type: str  # "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlockDict(TypedDict):
    """Tool result content block in user messages."""

    type: str  # "tool_result"
    tool_use_id: str
    content: str | list[dict[str, Any]]
    is_error: NotRequired[bool]  # Optional - defaults to False


# Union type for all content block types
MessageContentDict = TextBlockDict | ToolUseBlockDict | ToolResultBlockDict


class UserMessageDict(TypedDict):
    """User message data structure."""

    role: str  # "user"
    content: str | list[ToolResultBlockDict]


class AssistantMessageDict(TypedDict):
    """Assistant message data structure (API response)."""

    role: str  # "assistant"
    content: list[TextBlockDict | ToolUseBlockDict]
    model: str
    id: str
    type: str
    stop_reason: str | None
    stop_sequence: str | None
    usage: UsageDict


class ToolUseResultDict(TypedDict):
    """Tool execution result metadata."""

    stdout: str
    stderr: str
    interrupted: bool
    isImage: bool


class SummaryEntry(TypedDict):
    """Summary entry in JSONL file."""

    type: str  # "summary"
    summary: str
    leafUuid: str


class BaseMessageEntry(TypedDict):
    """Base fields common to both user and assistant message entries."""

    type: str  # "user" or "assistant"
    uuid: str
    timestamp: str  # ISO format datetime
    parentUuid: str | None
    isSidechain: bool
    userType: str
    cwd: str
    sessionId: str
    version: str
    gitBranch: str


class UserEntry(BaseMessageEntry):
    """User message entry in JSONL file."""

    type: str  # "user"
    message: UserMessageDict
    toolUseResult: NotRequired[ToolUseResultDict]


class AssistantEntry(BaseMessageEntry):
    """Assistant message entry in JSONL file."""

    type: str  # "assistant"
    message: AssistantMessageDict
    requestId: str


# Union type for all JSONL entry types
JSONLEntry = SummaryEntry | UserEntry | AssistantEntry


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

    Content is always a list of MessageContentDict blocks:
    - For user text messages: Single TextBlockDict with the message text
    - For assistant messages: List of text blocks and/or tool use blocks
    - For user tool results: List of ToolResultBlockDict blocks
    """

    uuid: str
    timestamp: datetime
    role: SessionMessageRole
    content: list[MessageContentDict]
    line_num: int  # Line number in the JSONL file (1-indexed)
    is_sidechain: bool  # Whether this message is from a sidechain session

    @property
    def tool_calls(self) -> list[ToolUseBlockDict] | None:
        """Extract tool use blocks from content.

        Returns:
            List of tool use blocks if present (assistant messages), None otherwise
        """
        if self.role != SessionMessageRole.ASSISTANT:
            return None
        tool_calls_list = [block for block in self.content if block.get("type") == "tool_use"]
        return cast(list[ToolUseBlockDict], tool_calls_list) if tool_calls_list else None

    @property
    def tool_results(self) -> list[ToolResultBlockDict] | None:
        """Extract tool result blocks from content.

        Returns:
            List of tool result blocks if present (user messages), None otherwise
        """
        if self.role != SessionMessageRole.USER:
            return None
        tool_results_list = [block for block in self.content if block.get("type") == "tool_result"]
        return cast(list[ToolResultBlockDict], tool_results_list) if tool_results_list else None

    @property
    def text_content(self) -> str:
        """Extract text content from the message.

        Returns:
            Extracted text content, or empty string if no text content
        """
        text_parts = []
        for block in self.content:
            if block.get("type") == "text":
                text_parts.append(block["text"])
        return "\n".join(text_parts)


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

    @staticmethod
    def encode_path_for_claude_projects(path: str) -> str:
        """Encode a filesystem path to Claude's project directory format.

        Claude encodes working directory paths by replacing '/' and '.' with '-' and
        prepending a '-' prefix.

        Example: /Users/foo/bar → -Users-foo-bar
        """
        return "-" + path.lstrip("/").replace("/", "-").replace(".", "-")

    def _extract_cwd_from_session_file(self, session_file: Path) -> str:
        """Extract the working directory from a session file.

        Reads the JSONL file line by line until finding an entry with a 'cwd' field.

        Args:
            session_file: Path to the session JSONL file

        Returns:
            The cwd value from the first entry containing it

        Raises:
            ValueError: If no entry with 'cwd' field is found
        """
        with session_file.open("r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if "cwd" in entry:
                        return entry["cwd"]
                except json.JSONDecodeError:
                    continue

        raise ValueError(f"No 'cwd' entry found in session file: {session_file}")

    async def migrate_session_to_directory(
        self,
        session_id: str,
        new_working_dir: str,
    ) -> Path | None:
        """Migrate a session file to a new working directory.

        Finds the session file automatically, moves the session JSONL file and
        optional session directory (containing tool-results) to the new project
        directory, then performs in-place path replacement using sed.

        Args:
            session_id: The Claude Code session ID
            new_working_dir: The new working directory path

        Returns:
            Path to the new session file location, or None if already in correct location

        Raises:
            FileNotFoundError: If the session file doesn't exist
            ValueError: If no 'cwd' entry found in session file
            ShellCommandExecutionError: If sed command fails
        """
        # Find the session file
        old_session_file = self.find_session_file(session_id)
        old_project_dir = old_session_file.parent

        # Calculate new project directory
        new_encoded_path = self.encode_path_for_claude_projects(new_working_dir)
        new_project_dir = self.claude_projects_dir / new_encoded_path

        # Skip if already in the correct location
        if old_project_dir == new_project_dir:
            logfire.debug(f"Session {session_id} already in correct location: {new_working_dir}")
            return None

        # Create new project directory if needed
        new_project_dir.mkdir(parents=True, exist_ok=True)

        # Move the session file
        new_session_file = new_project_dir / old_session_file.name
        shutil.move(str(old_session_file), str(new_session_file))
        logfire.info(f"Moved session file from {old_session_file} to {new_session_file}")

        # Move the session directory if it exists (contains tool-results)
        old_session_dir = old_project_dir / session_id
        if old_session_dir.exists() and old_session_dir.is_dir():
            new_session_dir = new_project_dir / session_id
            shutil.move(str(old_session_dir), str(new_session_dir))
            logfire.info(f"Moved session directory from {old_session_dir} to {new_session_dir}")

        # Extract old working directory from session file content
        old_working_dir = self._extract_cwd_from_session_file(old_session_file)
        # Perform in-place path replacement using sed
        # Use '|' as delimiter since paths contain '/'
        # macOS sed requires '' after -i, Linux doesn't
        if platform.system() == "Darwin":
            sed_cmd = ["sed", "-i", "", f"s|{old_working_dir}|{new_working_dir}|g", str(new_session_file)]
        else:
            sed_cmd = ["sed", "-i", f"s|{old_working_dir}|{new_working_dir}|g", str(new_session_file)]

        await execute_shell_command(sed_cmd)
        logfire.info(f"Replaced paths in session file: {old_working_dir} → {new_working_dir}")

        return new_session_file

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

        Malformed JSONL entries (invalid JSON, missing required fields, or unexpected
        data formats) are logged and skipped, allowing the rest of the session to be parsed.

        Args:
            session_id: The Claude Code session ID

        Returns:
            List of SessionMessage objects in chronological order

        Raises:
            FileNotFoundError: If Claude projects directory or session file doesn't exist
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
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logfire.warning(f"Skipping malformed JSONL entry at line {line_num}: {e}")
                    continue

        return messages

    def _parse_session_message(self, entry: JSONLEntry, line_num: int) -> SessionMessage | None:
        """Parse a JSONL entry into a SessionMessage with full data.

        Args:
            entry: Dictionary parsed from a JSONL line
            line_num: Line number in the JSONL file (1-indexed)

        Returns:
            SessionMessage with complete data, or None if not a message type

        Raises:
            KeyError: If required fields are missing
            ValueError: If message data has unexpected format
        """
        msg_type = entry["type"]

        # Only parse user and assistant messages
        if msg_type not in ("user", "assistant"):
            return None

        # Extract content - required field
        content_raw = entry["message"]["content"]

        # Convert string content to TextBlockDict for consistency
        if isinstance(content_raw, str):
            content = [TextBlockDict(type="text", text=content_raw)]
        else:
            # Validate and parse list content
            content = content_raw

        return SessionMessage(
            uuid=entry["uuid"],
            timestamp=datetime.fromisoformat(entry["timestamp"]),
            role=SessionMessageRole.USER if msg_type == "user" else SessionMessageRole.ASSISTANT,
            content=content,
            line_num=line_num,
            is_sidechain=entry["isSidechain"],
        )

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
