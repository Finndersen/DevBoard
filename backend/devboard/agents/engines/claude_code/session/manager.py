"""High-level service for browsing Claude Code projects and sessions."""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from devboard.agents.engines.claude_code.session.event_converter import session_messages_to_events
from devboard.agents.engines.claude_code.session.file_locator import find_session_file
from devboard.agents.engines.claude_code.session.migrator import ClaudeCodeSessionMigrator
from devboard.agents.engines.claude_code.session.service import ClaudeCodeSessionService
from devboard.agents.events import ConversationEvent
from devboard.db.repositories.claude_project import ClaudeProjectCacheRepository
from devboard.integrations.shell import execute_shell_command

# Maximum number of lines to scan when extracting first user message label
_LABEL_SCAN_LIMIT = 50
# Maximum length for session labels (characters)
_LABEL_MAX_LENGTH = 200

_IMPLEMENTATION_MESSAGE_PREFIX = "Implement the following plan:"
_TRANSCRIPT_REF_PATTERN = re.compile(
    r"read the full transcript at:\s+\S+/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl"
)


@dataclass
class ClaudeCodeProjectInfo:
    """Information about a Claude Code project."""

    path: str
    encoded_path: str
    last_activity: datetime | None
    session_count: int


@dataclass
class ClaudeCodeSessionInfo:
    """Information about a single Claude Code session file."""

    session_id: str
    label: str
    last_activity: datetime
    file_size: int
    start_time: datetime
    is_empty: bool
    linked_session_id: str | None = None
    session_role: str | None = None  # "plan" | "implementation" | None


@dataclass
class SessionSearchResult:
    """A ripgrep match result from searching session files."""

    session_id: str
    project_encoded_path: str
    line_number: int
    line_content: str
    message_uuid: str | None
    text_snippet: str | None


class ClaudeSessionManager:
    """Orchestrates project and session listing for the Claude Code session viewer."""

    def __init__(self, project_cache: ClaudeProjectCacheRepository) -> None:
        self._project_cache = project_cache
        self._session_service = ClaudeCodeSessionService()
        self.claude_projects_dir = Path.home() / ".claude" / "projects"

    def list_projects(self) -> list[ClaudeCodeProjectInfo]:
        """List all Claude Code projects ordered by last activity descending."""
        dir_mtimes = self._scan_project_dir_mtimes()
        cached_paths = self._project_cache.get_all()

        # Evict stale cache entries for directories that no longer exist
        stale = set(cached_paths) - set(dir_mtimes)
        if stale:
            self._project_cache.delete_encoded_paths(stale)

        results: list[ClaudeCodeProjectInfo] = []
        for encoded_path, mtime in dir_mtimes.items():
            project_dir = self.claude_projects_dir / encoded_path
            jsonl_files = list(project_dir.glob("*.jsonl"))
            if not jsonl_files:
                continue

            path = cached_paths.get(encoded_path)
            if path is None:
                path = self._extract_cwd_from_project_dir(jsonl_files) or encoded_path
                self._project_cache.set_path(encoded_path, path)

            results.append(
                ClaudeCodeProjectInfo(
                    path=path,
                    encoded_path=encoded_path,
                    last_activity=mtime,
                    session_count=len(jsonl_files),
                )
            )

        results.sort(key=lambda p: p.last_activity or datetime.min, reverse=True)
        return results

    def _extract_cwd_from_project_dir(self, jsonl_files: list[Path]) -> str | None:
        """Read JSONL files to extract the cwd field from the first entry that has it."""
        for jsonl_file in jsonl_files:
            try:
                with jsonl_file.open("r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        cwd = entry.get("cwd")
                        if cwd:
                            return cwd
            except (OSError, json.JSONDecodeError):
                continue
        return None

    def _scan_project_dir_mtimes(self) -> dict[str, datetime]:
        """Scan ~/.claude/projects/ and return a map of directory name to mtime."""
        try:
            result: dict[str, datetime] = {}
            for entry in os.scandir(self.claude_projects_dir):
                if not entry.is_dir():
                    continue
                try:
                    result[entry.name] = datetime.fromtimestamp(entry.stat().st_mtime)
                except OSError:
                    continue
            return result
        except FileNotFoundError:
            return {}

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

        # Build reverse mapping for O(1) lookup
        impl_to_plan: dict[str, str] = {impl: plan for plan, impl in plan_to_impl.items()}

        # Fallback: transcript-reference detection for sessions not yet linked via sessionId
        for jsonl_file in jsonl_files:
            session_id = jsonl_file.stem
            if session_id in plan_to_impl or session_id in impl_to_plan:
                continue
            plan_id = self._extract_plan_session_id_from_transcript_ref(jsonl_file)
            if plan_id and plan_id in all_session_ids:
                impl_to_plan[session_id] = plan_id
                if plan_id not in plan_to_impl:
                    plan_to_impl[plan_id] = session_id

        sessions: list[ClaudeCodeSessionInfo] = []
        for jsonl_file in jsonl_files:
            session_id = jsonl_file.stem
            stat = jsonl_file.stat()

            if session_id in custom_titles:
                label = custom_titles[session_id]
                is_empty = False
            else:
                label, is_empty = self._extract_first_user_message_label(jsonl_file)

            # Determine session role and linked session
            if session_id in plan_to_impl:
                session_role: str | None = "plan"
                linked_session_id: str | None = plan_to_impl[session_id]
            elif session_id in impl_to_plan:
                session_role = "implementation"
                linked_session_id = impl_to_plan[session_id]
            else:
                session_role = None
                linked_session_id = None

            sessions.append(
                ClaudeCodeSessionInfo(
                    session_id=session_id,
                    label=label,
                    last_activity=datetime.fromtimestamp(stat.st_mtime),
                    file_size=stat.st_size,
                    start_time=datetime.fromtimestamp(getattr(stat, "st_birthtime", stat.st_ctime)),
                    is_empty=is_empty,
                    linked_session_id=linked_session_id,
                    session_role=session_role,
                )
            )

        sessions.sort(key=lambda s: s.last_activity, reverse=True)
        return sessions

    def _extract_internal_session_id(self, jsonl_file: Path) -> str | None:
        """Read session JSONL entries until a sessionId field is found."""
        try:
            with jsonl_file.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    session_id = entry.get("sessionId")
                    if session_id is not None:
                        return session_id
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        return None

    def _extract_plan_session_id_from_transcript_ref(self, jsonl_file: Path) -> str | None:
        """Scan for the implementation phase user message and extract the plan session reference.

        DevBoard's implementation phase agent receives a user message starting with
        "Implement the following plan:" that also contains:
        "read the full transcript at: /path/to/<plan-session-id>.jsonl"

        Returns the plan session ID UUID if found, otherwise None.
        """
        try:
            with jsonl_file.open("r") as f:
                for i, line in enumerate(f):
                    if i >= _LABEL_SCAN_LIMIT:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    if entry.get("type") != "user":
                        continue
                    content = entry.get("message", {}).get("content", "")
                    text = self._extract_text_from_content(content)
                    if not text.startswith(_IMPLEMENTATION_MESSAGE_PREFIX):
                        continue
                    match = _TRANSCRIPT_REF_PATTERN.search(text)
                    if match:
                        return match.group(1)
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        return None

    def _extract_first_user_message_label(self, jsonl_file: Path) -> tuple[str, bool]:
        """Read the first genuine user message text from a session file as a label.

        Returns:
            A tuple of (label, is_empty) where is_empty is True if no genuine user
            message was found (only hook-injected or meta messages).
        """
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
                    if entry.get("isMeta") or entry.get("isCompactSummary"):
                        continue

                    content = entry.get("message", {}).get("content", "")
                    text = self._extract_text_from_content(content)

                    if not text:
                        continue
                    # Skip local commands, hooks, caveats, and tool interruptions
                    if text.startswith(("<bash-", "<command-", "<local-command-", "[Request interrupted")):
                        continue

                    return text[:_LABEL_MAX_LENGTH], False
        except (OSError, KeyError):
            pass

        return "No messages", True

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

    def locate_session(self, session_id: str) -> str:
        """Return the encoded project path for a given session ID.

        Raises:
            FileNotFoundError: If the session file cannot be found.
        """
        session_file = find_session_file(session_id, self.claude_projects_dir)
        return session_file.parent.name

    async def get_sub_agent_messages(self, session_id: str, agent_id: str) -> list[ConversationEvent]:
        """Load full conversation events for a sub-agent session.

        Raises:
            ValueError: If agent_id contains invalid characters.
            FileNotFoundError: If the sub-agent session file cannot be found.
        """
        messages = self._session_service.load_sub_agent_session_messages(session_id, agent_id)
        return session_messages_to_events(messages, include_sidechain=True)

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
            raw_line = match_data.get("lines", {}).get("text", "").strip()
            line_content = raw_line[:500]

            if not session_id or not project_encoded_path:
                continue

            message_uuid: str | None = None
            text_snippet: str | None = None
            try:
                jsonl_entry = json.loads(raw_line)
                message_uuid = jsonl_entry.get("uuid")
                content = jsonl_entry.get("message", {}).get("content")
                if isinstance(content, list):
                    text_parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    joined = "\n".join(text_parts)
                    text_snippet = joined[:200] if joined else None
                elif isinstance(content, str):
                    text_snippet = content[:200] if content else None
            except (json.JSONDecodeError, AttributeError):
                pass

            search_results.append(
                SessionSearchResult(
                    session_id=session_id,
                    project_encoded_path=project_encoded_path,
                    line_number=line_number,
                    line_content=line_content,
                    message_uuid=message_uuid,
                    text_snippet=text_snippet,
                )
            )

        return search_results
