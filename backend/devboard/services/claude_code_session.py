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

logger = logging.getLogger(__name__)


class ClaudeCodeSessionService:
    """Service for reading and parsing Claude Code session history."""

    def __init__(self, project_working_directory: Path):
        """Initialize service with project working directory.

        Args:
            project_working_directory: The working directory of the project
                                      (used to locate session files)
        """
        self.project_cwd = project_working_directory
        self.claude_projects_dir = Path.home() / ".claude" / "projects"

    @staticmethod
    def _normalize_path(path: Path) -> str:
        """Convert a file path to Claude's normalized directory name.

        Claude Code normalizes paths by replacing all forward slashes with hyphens.

        Args:
            path: The file path to normalize

        Returns:
            Normalized directory name used by Claude Code

        Example:
            >>> _normalize_path(Path("/Users/finn/projects/DevBoard"))
            "-Users-finn-projects-DevBoard"
        """
        return str(path).replace("/", "-")

    def get_session_file_path(self, session_id: str) -> Path:
        """Resolve the JSONL file path for a given session ID.

        Args:
            session_id: The Claude Code session ID

        Returns:
            Path to the session JSONL file
        """
        normalized_dir = self._normalize_path(self.project_cwd)
        session_dir = self.claude_projects_dir / normalized_dir
        return session_dir / f"{session_id}.jsonl"

    def load_conversation_history(self, session_id: str) -> list[ConversationMessage]:
        """Load conversation history from a Claude Code session.

        Reads the JSONL session file and converts user and assistant text messages
        to ConversationMessage objects. Filters out tool calls, summaries, and
        other non-conversational message types.

        Args:
            session_id: The Claude Code session ID

        Returns:
            List of ConversationMessage objects in chronological order

        Raises:
            FileNotFoundError: If the session file doesn't exist
            json.JSONDecodeError: If the JSONL file is malformed
            PermissionError: If unable to read the session file
        """
        session_file = self.get_session_file_path(session_id)

        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")

        messages: list[ConversationMessage] = []

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
