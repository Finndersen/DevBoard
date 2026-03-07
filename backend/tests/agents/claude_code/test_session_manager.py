"""Tests for ClaudeSessionManager."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.agents.engines.claude_code.config_parser import ClaudeConfigProject
from devboard.agents.engines.claude_code.session.manager import (
    ClaudeSessionManager,
    SessionSearchResult,
)
from devboard.integrations.shell import ShellCommandResult


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def _make_user_entry(content: str, is_meta: bool = False, session_id: str = "sess-1") -> dict:
    return {
        "type": "user",
        "uuid": "u1",
        "timestamp": "2025-01-01T00:00:00.000Z",
        "isSidechain": False,
        "sessionId": session_id,
        "message": {"role": "user", "content": content},
        **({"isMeta": True} if is_meta else {}),
    }


def _make_summary_entry() -> dict:
    return {"type": "summary", "summary": "summary text", "leafUuid": "l1"}


@pytest.fixture
def claude_projects_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".claude" / "projects"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def manager(claude_projects_dir: Path) -> ClaudeSessionManager:
    m = ClaudeSessionManager.__new__(ClaudeSessionManager)
    m._config_parser = MagicMock()
    m._session_service = MagicMock()
    m.claude_projects_dir = claude_projects_dir
    return m


class TestListProjects:
    def test_returns_projects_with_sessions(self, manager: ClaudeSessionManager, claude_projects_dir: Path) -> None:
        project_dir = claude_projects_dir / "-Users-foo-myproject"
        project_dir.mkdir()
        (project_dir / "sess-1.jsonl").write_text("{}\n")

        manager._config_parser.load_projects.return_value = [
            ClaudeConfigProject(
                path="/Users/foo/myproject",
                last_session_id="sess-1",
                last_cost=0.01,
                last_duration=None,
                last_lines_added=5,
                last_lines_removed=2,
            )
        ]
        manager._session_service.encode_path_for_claude_projects = lambda p: (
            "-" + p.lstrip("/").replace("/", "-").replace(".", "-")
        )

        projects = manager.list_projects()

        assert len(projects) == 1
        assert projects[0].path == "/Users/foo/myproject"
        assert projects[0].encoded_path == "-Users-foo-myproject"
        assert projects[0].session_count == 1
        assert projects[0].last_cost == 0.01
        assert projects[0].last_lines_added == 5
        assert projects[0].last_lines_removed == 2

    def test_skips_projects_with_no_sessions(self, manager: ClaudeSessionManager, claude_projects_dir: Path) -> None:
        project_dir = claude_projects_dir / "-Users-foo-empty"
        project_dir.mkdir()
        # No .jsonl files

        manager._config_parser.load_projects.return_value = [
            ClaudeConfigProject(
                path="/Users/foo/empty",
                last_session_id=None,
                last_cost=None,
                last_duration=None,
                last_lines_added=None,
                last_lines_removed=None,
            )
        ]
        manager._session_service.encode_path_for_claude_projects = lambda p: (
            "-" + p.lstrip("/").replace("/", "-").replace(".", "-")
        )

        projects = manager.list_projects()
        assert projects == []

    def test_skips_projects_with_no_directory(self, manager: ClaudeSessionManager) -> None:
        manager._config_parser.load_projects.return_value = [
            ClaudeConfigProject(
                path="/Users/foo/nonexistent",
                last_session_id=None,
                last_cost=None,
                last_duration=None,
                last_lines_added=None,
                last_lines_removed=None,
            )
        ]
        manager._session_service.encode_path_for_claude_projects = lambda p: (
            "-" + p.lstrip("/").replace("/", "-").replace(".", "-")
        )

        projects = manager.list_projects()
        assert projects == []

    def test_orders_by_last_activity_descending(self, manager: ClaudeSessionManager, claude_projects_dir: Path) -> None:
        for name in ["-Users-foo-old", "-Users-foo-new"]:
            d = claude_projects_dir / name
            d.mkdir()
            (d / "sess.jsonl").write_text("{}\n")

        # Patch mtime so "new" project has more recent mtime
        import os
        import time

        old_dir = claude_projects_dir / "-Users-foo-old"
        new_dir = claude_projects_dir / "-Users-foo-new"
        old_session = old_dir / "sess.jsonl"
        new_session = new_dir / "sess.jsonl"

        # Set different modification times
        os.utime(old_session, (time.time() - 3600, time.time() - 3600))
        os.utime(new_session, (time.time(), time.time()))

        manager._config_parser.load_projects.return_value = [
            ClaudeConfigProject(
                path="/Users/foo/old",
                last_session_id="sess",
                last_cost=None,
                last_duration=None,
                last_lines_added=None,
                last_lines_removed=None,
            ),
            ClaudeConfigProject(
                path="/Users/foo/new",
                last_session_id="sess",
                last_cost=None,
                last_duration=None,
                last_lines_added=None,
                last_lines_removed=None,
            ),
        ]
        manager._session_service.encode_path_for_claude_projects = lambda p: (
            "-" + p.lstrip("/").replace("/", "-").replace(".", "-")
        )

        projects = manager.list_projects()

        assert len(projects) == 2
        assert projects[0].path == "/Users/foo/new"
        assert projects[1].path == "/Users/foo/old"


class TestExtractFirstUserMessageLabel:
    def test_extracts_simple_text_message(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("Hello, world!")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label = manager._extract_first_user_message_label(jsonl)
        assert label == "Hello, world!"

    def test_skips_non_user_entries(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_summary_entry(), _make_user_entry("First real message")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label = manager._extract_first_user_message_label(jsonl)
        assert label == "First real message"

    def test_skips_meta_user_entries(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("meta content", is_meta=True), _make_user_entry("Real message")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label = manager._extract_first_user_message_label(jsonl)
        assert label == "Real message"

    def test_skips_command_entries(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("<command-name>clear</command-name>"), _make_user_entry("Real message")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label = manager._extract_first_user_message_label(jsonl)
        assert label == "Real message"

    def test_returns_no_messages_when_empty(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        jsonl.write_text("")

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label = manager._extract_first_user_message_label(jsonl)
        assert label == "No messages"

    def test_truncates_long_messages(self, tmp_path: Path) -> None:
        long_text = "x" * 300
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry(long_text)])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label = manager._extract_first_user_message_label(jsonl)
        assert len(label) == 200


class TestResolveCustomTitles:
    @pytest.mark.asyncio
    async def test_parses_ripgrep_output(self, tmp_path: Path) -> None:
        match_line = json.dumps({"type": "custom-title", "sessionId": "sess-1", "customTitle": "My Title"})

        with patch("devboard.agents.engines.claude_code.session.manager.execute_shell_command") as mock_cmd:
            mock_cmd.return_value = ShellCommandResult(stdout=match_line + "\n", stderr="", returncode=0)
            manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
            titles = await manager._resolve_custom_titles(tmp_path)

        assert titles == {"sess-1": "My Title"}

    @pytest.mark.asyncio
    async def test_last_title_wins_for_multiple_renames(self, tmp_path: Path) -> None:
        lines = "\n".join(
            [
                json.dumps({"type": "custom-title", "sessionId": "sess-1", "customTitle": "First Title"}),
                json.dumps({"type": "custom-title", "sessionId": "sess-1", "customTitle": "Final Title"}),
            ]
        )

        with patch("devboard.agents.engines.claude_code.session.manager.execute_shell_command") as mock_cmd:
            mock_cmd.return_value = ShellCommandResult(stdout=lines + "\n", stderr="", returncode=0)
            manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
            titles = await manager._resolve_custom_titles(tmp_path)

        assert titles == {"sess-1": "Final Title"}

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_matches(self, tmp_path: Path) -> None:
        with patch("devboard.agents.engines.claude_code.session.manager.execute_shell_command") as mock_cmd:
            mock_cmd.return_value = ShellCommandResult(stdout="", stderr="", returncode=1)
            manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
            titles = await manager._resolve_custom_titles(tmp_path)

        assert titles == {}


class TestListSessions:
    @pytest.mark.asyncio
    async def test_returns_sessions_ordered_by_mtime(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        import os
        import time

        project_dir = claude_projects_dir / "-Users-foo-proj"
        project_dir.mkdir()

        old_file = project_dir / "old-sess.jsonl"
        new_file = project_dir / "new-sess.jsonl"
        _write_jsonl(old_file, [_make_user_entry("Old session")])
        _write_jsonl(new_file, [_make_user_entry("New session")])

        os.utime(old_file, (time.time() - 3600, time.time() - 3600))
        os.utime(new_file, (time.time(), time.time()))

        with patch.object(manager, "_resolve_custom_titles", new=AsyncMock(return_value={})):
            sessions = await manager.list_sessions("-Users-foo-proj")

        assert len(sessions) == 2
        assert sessions[0].session_id == "new-sess"
        assert sessions[1].session_id == "old-sess"
        assert sessions[0].label == "New session"

    @pytest.mark.asyncio
    async def test_uses_custom_title_when_present(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-proj"
        project_dir.mkdir()
        _write_jsonl(project_dir / "sess-1.jsonl", [_make_user_entry("Original message")])

        with patch.object(manager, "_resolve_custom_titles", new=AsyncMock(return_value={"sess-1": "My Custom Title"})):
            sessions = await manager.list_sessions("-Users-foo-proj")

        assert len(sessions) == 1
        assert sessions[0].label == "My Custom Title"

    @pytest.mark.asyncio
    async def test_raises_file_not_found_for_missing_directory(self, manager: ClaudeSessionManager) -> None:
        with pytest.raises(FileNotFoundError):
            await manager.list_sessions("-nonexistent-project")


class TestSearchSessions:
    @pytest.mark.asyncio
    async def test_parses_ripgrep_json_output(self, manager: ClaudeSessionManager, claude_projects_dir: Path) -> None:
        rg_output = json.dumps(
            {
                "type": "match",
                "data": {
                    "path": {"text": str(claude_projects_dir / "-Users-foo-proj" / "sess-abc.jsonl")},
                    "line_number": 5,
                    "lines": {"text": '{"type":"user","message":{"content":"hello"}}'},
                },
            }
        )

        with patch("devboard.agents.engines.claude_code.session.manager.execute_shell_command") as mock_cmd:
            mock_cmd.return_value = ShellCommandResult(stdout=rg_output + "\n", stderr="", returncode=0)
            results = await manager.search_sessions("hello")

        assert len(results) == 1
        assert results[0] == SessionSearchResult(
            session_id="sess-abc",
            project_encoded_path="-Users-foo-proj",
            line_number=5,
            line_content='{"type":"user","message":{"content":"hello"}}',
        )

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_matches(self, manager: ClaudeSessionManager) -> None:
        with patch("devboard.agents.engines.claude_code.session.manager.execute_shell_command") as mock_cmd:
            mock_cmd.return_value = ShellCommandResult(stdout="", stderr="", returncode=1)
            results = await manager.search_sessions("nonexistent")

        assert results == []

    @pytest.mark.asyncio
    async def test_scopes_search_to_project_when_project_path_provided(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        manager._session_service.encode_path_for_claude_projects = lambda p: (
            "-" + p.lstrip("/").replace("/", "-").replace(".", "-")
        )

        with patch("devboard.agents.engines.claude_code.session.manager.execute_shell_command") as mock_cmd:
            mock_cmd.return_value = ShellCommandResult(stdout="", stderr="", returncode=1)
            await manager.search_sessions("query", project_path="/Users/foo/proj")

        call_args = mock_cmd.call_args[0][0]
        assert str(claude_projects_dir / "-Users-foo-proj") in call_args
