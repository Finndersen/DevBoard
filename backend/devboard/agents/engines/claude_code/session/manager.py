"""High-level service for browsing Claude Code projects and sessions."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from devboard.agents.engines.claude_code.config_parser import ClaudeConfigParser
from devboard.agents.engines.claude_code.session.event_converter import session_messages_to_events
from devboard.agents.engines.claude_code.session.migrator import ClaudeCodeSessionMigrator
from devboard.agents.engines.claude_code.session.service import ClaudeCodeSessionService
from devboard.agents.events import ConversationEvent
from devboard.integrations.shell import execute_shell_command

# Maximum number of lines to scan when extracting first user message label
_LABEL_SCAN_LIMIT = 50
# Maximum length for session labels (characters)
_LABEL_MAX_LENGTH = 200


@dataclass
class ClaudeCodeProjectInfo:
    """Information about a Claude Code project."""

    path: str
    encoded_path: str
    last_activity: datetime | None
    last_cost: float | None
    last_lines_added: int | None
    last_lines_removed: int | None
    session_count: int


@dataclass
class ClaudeCodeSessionInfo:
    """Information about a single Claude Code session file."""

    session_id: str
    label: str
    last_activity: datetime
    file_size: int
    linked_session_id: str | None = None
    session_role: str | None = None  # "plan" | "implementation" | None


@dataclass
class SessionSearchResult:
    """A ripgrep match result from searching session files."""

    session_id: str
    project_encoded_path: str
    line_number: int
    line_content: str


class ClaudeSessionManager:
    """Orchestrates project and session listing for the Claude Code session viewer."""

    def __init__(self) -> None:
        self._config_parser = ClaudeConfigParser()
        self._session_service = ClaudeCodeSessionService()
        self.claude_projects_dir = Path.home() / ".claude" / "projects"

    def list_projects(self) -> list[ClaudeCodeProjectInfo]:
        """List all Claude Code projects ordered by last activity descending."""
        config_projects = self._config_parser.load_projects()

        results: list[ClaudeCodeProjectInfo] = []
        for config_project in config_projects:
            encoded_path = ClaudeCodeSessionMigrator.encode_path_for_claude_projects(config_project.path)
            project_dir = self.claude_projects_dir / encoded_path

            if not project_dir.is_dir():
                continue

            jsonl_files = list(project_dir.glob("*.jsonl"))
            session_count = len(jsonl_files)
            if session_count == 0:
                continue

            last_activity = self._resolve_project_last_activity(
                config_project.last_session_id, project_dir, jsonl_files
            )

            results.append(
                ClaudeCodeProjectInfo(
                    path=config_project.path,
                    encoded_path=encoded_path,
                    last_activity=last_activity,
                    last_cost=config_project.last_cost,
                    last_lines_added=config_project.last_lines_added,
                    last_lines_removed=config_project.last_lines_removed,
                    session_count=session_count,
                )
            )

        # Sort by last_activity descending, None values last
        results.sort(key=lambda p: p.last_activity or datetime.min, reverse=True)
        return results

    def _resolve_project_last_activity(
        self,
        last_session_id: str | None,
        project_dir: Path,
        jsonl_files: list[Path],
    ) -> datetime | None:
        """Resolve the last activity time for a project."""
        if last_session_id:
            specific_file = project_dir / f"{last_session_id}.jsonl"
            if specific_file.exists():
                return datetime.fromtimestamp(specific_file.stat().st_mtime)
            # Fall back to directory mtime
            return datetime.fromtimestamp(project_dir.stat().st_mtime)

        if jsonl_files:
            return max(datetime.fromtimestamp(f.stat().st_mtime) for f in jsonl_files)

        return None

    async def list_sessions(self, encoded_project_path: str) -> list[ClaudeCodeSessionInfo]:
        """List sessions for a project, ordered by last activity descending.

        Raises:
            FileNotFoundError: If the project directory does not exist.
        """
        project_dir = self.claude_projects_dir / encoded_project_path
        if not project_dir.is_dir():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")

        jsonl_files = list(project_dir.glob("*.jsonl"))
        custom_titles = await self._resolve_custom_titles(project_dir)

        # Map filename stem → internal sessionId for linkage detection
        file_to_internal_id: dict[str, str] = {}
        for jsonl_file in jsonl_files:
            internal_id = self._extract_internal_session_id(jsonl_file)
            if internal_id is not None:
                file_to_internal_id[jsonl_file.stem] = internal_id

        # Build plan_id → impl_id mapping for files where internal id ≠ filename stem
        all_session_ids = {f.stem for f in jsonl_files}
        plan_to_impl: dict[str, str] = {}
        for filename_stem, internal_id in file_to_internal_id.items():
            if filename_stem != internal_id and internal_id in all_session_ids:
                plan_to_impl[internal_id] = filename_stem

        sessions: list[ClaudeCodeSessionInfo] = []
        for jsonl_file in jsonl_files:
            session_id = jsonl_file.stem
            stat = jsonl_file.stat()
            last_activity = datetime.fromtimestamp(stat.st_mtime)
            file_size = stat.st_size

            if session_id in custom_titles:
                label = custom_titles[session_id]
            else:
                label = self._extract_first_user_message_label(jsonl_file)

            # Determine session role and linked session
            if session_id in plan_to_impl:
                session_role: str | None = "plan"
                linked_session_id: str | None = plan_to_impl[session_id]
            elif file_to_internal_id.get(session_id, session_id) != session_id:
                # This is an implementation file (internal_id ≠ filename_stem)
                # Only annotate if the referenced plan session exists
                internal_id = file_to_internal_id[session_id]
                if internal_id in all_session_ids:
                    session_role = "implementation"
                    linked_session_id = internal_id
                else:
                    session_role = None
                    linked_session_id = None
            else:
                session_role = None
                linked_session_id = None

            sessions.append(
                ClaudeCodeSessionInfo(
                    session_id=session_id,
                    label=label,
                    last_activity=last_activity,
                    file_size=file_size,
                    linked_session_id=linked_session_id,
                    session_role=session_role,
                )
            )

        sessions.sort(key=lambda s: s.last_activity, reverse=True)
        return sessions

    def _extract_internal_session_id(self, jsonl_file: Path) -> str | None:
        """Read the first JSON entry of a JSONL file and return its sessionId field."""
        try:
            with jsonl_file.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    return entry.get("sessionId")
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        return None

    def _extract_first_user_message_label(self, jsonl_file: Path) -> str:
        """Read the first genuine user message text from a session file as a label."""
        try:
            with jsonl_file.open("r") as f:
                for i, line in enumerate(f):
                    if i >= _LABEL_SCAN_LIMIT:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if entry.get("type") != "user":
                        continue
                    if entry.get("isMeta"):
                        continue

                    content = entry.get("message", {}).get("content", "")
                    text = self._extract_text_from_content(content)

                    if not text:
                        continue
                    # Skip slash command entries
                    if "<command-name>" in text:
                        continue

                    return text[:_LABEL_MAX_LENGTH]
        except (OSError, KeyError):
            pass

        return "No messages"

    @staticmethod
    def _extract_text_from_content(content: str | list) -> str:
        """Extract plain text from a message content field."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            return "\n".join(parts)
        return ""

    async def _resolve_custom_titles(self, project_dir: Path) -> dict[str, str]:
        """Run ripgrep to find custom-title entries and build a session_id → title map."""
        result = await execute_shell_command(
            ["rg", "--no-filename", "--no-line-number", '"type":"custom-title"', str(project_dir)],
            raise_on_error=False,
            timeout=15.0,
        )

        titles: dict[str, str] = {}
        if not result.stdout.strip():
            return titles

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                session_id = entry.get("sessionId")
                custom_title = entry.get("customTitle")
                if session_id and custom_title:
                    titles[session_id] = custom_title
            except json.JSONDecodeError:
                continue

        return titles

    async def get_session_messages(self, session_id: str) -> list[ConversationEvent]:
        """Load full conversation events for a session.

        Raises:
            FileNotFoundError: If the session file cannot be found.
        """
        session_messages = self._session_service.load_session_messages(session_id)
        return session_messages_to_events(session_messages)

    async def search_sessions(self, query: str, project_path: str | None = None) -> list[SessionSearchResult]:
        """Search session JSONL files using ripgrep.

        Args:
            query: The pattern to search for.
            project_path: Original filesystem path to scope search to a single project.
                          If None, searches all of ~/.claude/projects/.
        """
        if project_path:
            encoded_path = ClaudeCodeSessionMigrator.encode_path_for_claude_projects(project_path)
            search_dir = self.claude_projects_dir / encoded_path
        else:
            search_dir = self.claude_projects_dir

        result = await execute_shell_command(
            ["rg", "--line-number", "--no-heading", "--json", query, str(search_dir), "--glob", "*.jsonl"],
            raise_on_error=False,
            timeout=60.0,
        )

        search_results: list[SessionSearchResult] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") != "match":
                continue

            match_data = entry.get("data", {})
            file_path = Path(match_data.get("path", {}).get("text", ""))
            session_id = file_path.stem
            project_encoded_path = file_path.parent.name
            line_number = match_data.get("line_number", 0)
            line_content = match_data.get("lines", {}).get("text", "").strip()[:500]

            if not session_id or not project_encoded_path:
                continue

            search_results.append(
                SessionSearchResult(
                    session_id=session_id,
                    project_encoded_path=project_encoded_path,
                    line_number=line_number,
                    line_content=line_content,
                )
            )

        return search_results
