"""Tests for ClaudeSessionManager."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        "cwd": "/Users/foo/myproject",
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
def mock_cache() -> MagicMock:
    cache = MagicMock(spec=["get_all", "set_path", "delete_encoded_paths"])
    cache.get_all.return_value = {}
    return cache


@pytest.fixture
def manager(claude_projects_dir: Path, mock_cache: MagicMock) -> ClaudeSessionManager:
    m = ClaudeSessionManager.__new__(ClaudeSessionManager)
    m._project_cache = mock_cache
    m._session_service = MagicMock()
    m.claude_projects_dir = claude_projects_dir
    return m


class TestListProjects:
    def test_returns_all_projects_from_filesystem(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path, mock_cache: MagicMock
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-myproject"
        project_dir.mkdir()
        _write_jsonl(project_dir / "sess-1.jsonl", [_make_user_entry("Hello")])
        mock_cache.get_all.return_value = {}

        projects = manager.list_projects()

        assert len(projects) == 1
        assert projects[0].encoded_path == "-Users-foo-myproject"
        assert projects[0].session_count == 1

    def test_uses_cached_path_without_reading_jsonl(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path, mock_cache: MagicMock
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-myproject"
        project_dir.mkdir()
        (project_dir / "sess-1.jsonl").write_text("{}\n")
        mock_cache.get_all.return_value = {"-Users-foo-myproject": "/Users/foo/myproject"}

        projects = manager.list_projects()

        assert len(projects) == 1
        assert projects[0].path == "/Users/foo/myproject"
        mock_cache.set_path.assert_not_called()

    def test_populates_cache_from_cwd_on_first_encounter(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path, mock_cache: MagicMock
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-myproject"
        project_dir.mkdir()
        _write_jsonl(project_dir / "sess-1.jsonl", [{"cwd": "/Users/foo/myproject", "type": "user"}])
        mock_cache.get_all.return_value = {}

        projects = manager.list_projects()

        assert projects[0].path == "/Users/foo/myproject"
        mock_cache.set_path.assert_called_once_with("-Users-foo-myproject", "/Users/foo/myproject")

    def test_falls_back_to_encoded_path_when_no_cwd(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path, mock_cache: MagicMock
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-myproject"
        project_dir.mkdir()
        _write_jsonl(project_dir / "sess-1.jsonl", [{"type": "user", "message": {"content": "hi"}}])
        mock_cache.get_all.return_value = {}

        projects = manager.list_projects()

        assert projects[0].path == "-Users-foo-myproject"
        mock_cache.set_path.assert_called_once_with("-Users-foo-myproject", "-Users-foo-myproject")

    def test_evicts_stale_cache_entries(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path, mock_cache: MagicMock
    ) -> None:
        # Cached entry for a dir that no longer exists on filesystem
        mock_cache.get_all.return_value = {"-Users-foo-gone": "/Users/foo/gone"}

        manager.list_projects()

        mock_cache.delete_encoded_paths.assert_called_once_with({"-Users-foo-gone"})

    def test_skips_projects_with_no_sessions(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path, mock_cache: MagicMock
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-empty"
        project_dir.mkdir()
        # No .jsonl files
        mock_cache.get_all.return_value = {}

        projects = manager.list_projects()
        assert projects == []

    def test_orders_by_last_activity_descending(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path, mock_cache: MagicMock
    ) -> None:
        import os
        import time

        for name in ["-Users-foo-old", "-Users-foo-new"]:
            d = claude_projects_dir / name
            d.mkdir()
            (d / "sess.jsonl").write_text('{"cwd":"/Users/foo/' + name.split("-")[-1] + '"}\n')

        old_dir = claude_projects_dir / "-Users-foo-old"
        new_dir = claude_projects_dir / "-Users-foo-new"

        os.utime(old_dir, (time.time() - 3600, time.time() - 3600))
        os.utime(new_dir, (time.time(), time.time()))

        mock_cache.get_all.return_value = {
            "-Users-foo-old": "/Users/foo/old",
            "-Users-foo-new": "/Users/foo/new",
        }

        projects = manager.list_projects()

        assert len(projects) == 2
        assert projects[0].path == "/Users/foo/new"
        assert projects[1].path == "/Users/foo/old"


class TestExtractFirstUserMessageLabel:
    def test_extracts_simple_text_message(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("Hello, world!")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "Hello, world!"
        assert is_empty is False

    def test_skips_non_user_entries(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_summary_entry(), _make_user_entry("First real message")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "First real message"
        assert is_empty is False

    def test_skips_meta_user_entries(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("meta content", is_meta=True), _make_user_entry("Real message")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "Real message"
        assert is_empty is False

    def test_skips_command_entries(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("<command-name>clear</command-name>"), _make_user_entry("Real message")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "Real message"
        assert is_empty is False

    def test_returns_no_messages_when_empty(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        jsonl.write_text("")

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "No messages"
        assert is_empty is True

    def test_truncates_long_messages(self, tmp_path: Path) -> None:
        long_text = "x" * 300
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry(long_text)])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert len(label) == 200
        assert is_empty is False

    def test_only_command_name_tags_is_empty(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("<command-name>clear</command-name>")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "No messages"
        assert is_empty is True

    def test_only_local_command_caveat_is_empty(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("<local-command-caveat>some caveat</local-command-caveat>")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "No messages"
        assert is_empty is True

    def test_only_local_command_stdout_is_empty(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("<local-command-stdout>some output</local-command-stdout>")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "No messages"
        assert is_empty is True

    def test_only_meta_messages_is_empty(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("meta content", is_meta=True)])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "No messages"
        assert is_empty is True

    def test_interrupted_message_is_empty(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("[Request interrupted by user for tool use]")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "No messages"
        assert is_empty is True

    def test_tag_in_middle_of_message_is_not_empty(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "sess.jsonl"
        _write_jsonl(jsonl, [_make_user_entry("Hello <command-name>clear</command-name>")])

        manager = ClaudeSessionManager.__new__(ClaudeSessionManager)
        label, is_empty = manager._extract_first_user_message_label(jsonl)
        assert label == "Hello <command-name>clear</command-name>"
        assert is_empty is False


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


class TestLinkedSessions:
    @pytest.mark.asyncio
    async def test_detects_plan_and_implementation_pair(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-proj"
        project_dir.mkdir()
        _write_jsonl(project_dir / "plan-id.jsonl", [_make_user_entry("Plan message", session_id="plan-id")])
        _write_jsonl(project_dir / "impl-id.jsonl", [_make_user_entry("Impl message", session_id="plan-id")])

        with patch.object(manager, "_resolve_custom_titles", new=AsyncMock(return_value={})):
            sessions = await manager.list_sessions("-Users-foo-proj")

        by_id = {s.session_id: s for s in sessions}
        assert by_id["plan-id"].session_role == "plan"
        assert by_id["plan-id"].linked_session_id == "impl-id"
        assert by_id["impl-id"].session_role == "implementation"
        assert by_id["impl-id"].linked_session_id == "plan-id"

    @pytest.mark.asyncio
    async def test_standalone_session_has_no_role(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-proj"
        project_dir.mkdir()
        _write_jsonl(project_dir / "sess-1.jsonl", [_make_user_entry("Hello", session_id="sess-1")])

        with patch.object(manager, "_resolve_custom_titles", new=AsyncMock(return_value={})):
            sessions = await manager.list_sessions("-Users-foo-proj")

        assert len(sessions) == 1
        assert sessions[0].session_role is None
        assert sessions[0].linked_session_id is None

    @pytest.mark.asyncio
    async def test_orphaned_implementation_treated_as_standalone(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-proj"
        project_dir.mkdir()
        # impl-id references missing-plan-id, but that file doesn't exist
        _write_jsonl(
            project_dir / "impl-id.jsonl",
            [_make_user_entry("Impl message", session_id="missing-plan-id")],
        )

        with patch.object(manager, "_resolve_custom_titles", new=AsyncMock(return_value={})):
            sessions = await manager.list_sessions("-Users-foo-proj")

        assert len(sessions) == 1
        assert sessions[0].session_role is None
        assert sessions[0].linked_session_id is None

    @pytest.mark.asyncio
    async def test_mixed_standalone_and_paired_sessions(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-proj"
        project_dir.mkdir()
        _write_jsonl(project_dir / "standalone.jsonl", [_make_user_entry("Standalone", session_id="standalone")])
        _write_jsonl(project_dir / "plan-id.jsonl", [_make_user_entry("Plan", session_id="plan-id")])
        _write_jsonl(project_dir / "impl-id.jsonl", [_make_user_entry("Impl", session_id="plan-id")])

        with patch.object(manager, "_resolve_custom_titles", new=AsyncMock(return_value={})):
            sessions = await manager.list_sessions("-Users-foo-proj")

        by_id = {s.session_id: s for s in sessions}
        assert by_id["standalone"].session_role is None
        assert by_id["standalone"].linked_session_id is None
        assert by_id["plan-id"].session_role == "plan"
        assert by_id["plan-id"].linked_session_id == "impl-id"
        assert by_id["impl-id"].session_role == "implementation"
        assert by_id["impl-id"].linked_session_id == "plan-id"

    @pytest.mark.asyncio
    async def test_file_history_snapshot_first_line_detected_correctly(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        """Sessions starting with file-history-snapshot (no sessionId) are detected via next entry."""
        project_dir = claude_projects_dir / "-Users-foo-proj"
        project_dir.mkdir()
        snapshot_entry = {"type": "file-history-snapshot", "files": []}
        _write_jsonl(
            project_dir / "sess-1.jsonl",
            [snapshot_entry, _make_user_entry("Hello", session_id="sess-1")],
        )

        with patch.object(manager, "_resolve_custom_titles", new=AsyncMock(return_value={})):
            sessions = await manager.list_sessions("-Users-foo-proj")

        assert len(sessions) == 1
        assert sessions[0].session_role is None
        assert sessions[0].linked_session_id is None

    @pytest.mark.asyncio
    async def test_transcript_ref_links_implementation_to_plan(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        """Impl session with 'Implement the following plan:' message referencing plan JSONL is linked."""
        project_dir = claude_projects_dir / "-Users-foo-proj"
        project_dir.mkdir()
        plan_id = "b3c097c9-6212-452d-9a96-0036b096547f"
        impl_id = "f32dd876-d42e-4911-adbf-3ba58cc38afb"

        _write_jsonl(project_dir / f"{plan_id}.jsonl", [_make_user_entry("Plan task", session_id=plan_id)])
        impl_message = (
            f"Implement the following plan:\n\n...\n\n"
            f"read the full transcript at: /Users/finn/.claude/projects/proj/{plan_id}.jsonl"
        )
        _write_jsonl(
            project_dir / f"{impl_id}.jsonl",
            [_make_user_entry(impl_message, session_id=impl_id)],
        )

        with patch.object(manager, "_resolve_custom_titles", new=AsyncMock(return_value={})):
            sessions = await manager.list_sessions("-Users-foo-proj")

        by_id = {s.session_id: s for s in sessions}
        assert by_id[plan_id].session_role == "plan"
        assert by_id[plan_id].linked_session_id == impl_id
        assert by_id[impl_id].session_role == "implementation"
        assert by_id[impl_id].linked_session_id == plan_id

    @pytest.mark.asyncio
    async def test_transcript_ref_ignored_when_plan_not_in_project(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        """Impl session referencing a plan session not present in the project is treated as standalone."""
        project_dir = claude_projects_dir / "-Users-foo-proj"
        project_dir.mkdir()
        missing_plan_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        impl_id = "f32dd876-d42e-4911-adbf-3ba58cc38afb"

        impl_message = (
            f"Implement the following plan:\n\n...\n\n"
            f"read the full transcript at: /Users/finn/.claude/projects/proj/{missing_plan_id}.jsonl"
        )
        _write_jsonl(
            project_dir / f"{impl_id}.jsonl",
            [_make_user_entry(impl_message, session_id=impl_id)],
        )

        with patch.object(manager, "_resolve_custom_titles", new=AsyncMock(return_value={})):
            sessions = await manager.list_sessions("-Users-foo-proj")

        assert len(sessions) == 1
        assert sessions[0].session_role is None
        assert sessions[0].linked_session_id is None


class TestLocateSession:
    def test_returns_encoded_project_path_for_existing_session(
        self, manager: ClaudeSessionManager, claude_projects_dir: Path
    ) -> None:
        project_dir = claude_projects_dir / "-Users-foo-myproject"
        project_dir.mkdir()
        (project_dir / "sess-abc.jsonl").write_text("{}\n")

        result = manager.locate_session("sess-abc")

        assert result == "-Users-foo-myproject"

    def test_raises_file_not_found_for_missing_session(self, manager: ClaudeSessionManager) -> None:
        with pytest.raises(FileNotFoundError):
            manager.locate_session("nonexistent-session-id")


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
            message_uuid=None,
            text_snippet="hello",
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
            "-" + p.lstrip("/").replace("/", "-").replace(".", "-").replace("_", "-")
        )

        with patch("devboard.agents.engines.claude_code.session.manager.execute_shell_command") as mock_cmd:
            mock_cmd.return_value = ShellCommandResult(stdout="", stderr="", returncode=1)
            await manager.search_sessions("query", project_path="/Users/foo/proj")

        call_args = mock_cmd.call_args[0][0]
        assert str(claude_projects_dir / "-Users-foo-proj") in call_args
