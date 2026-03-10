"""Tests for ClaudeConfigParser."""

import json
from pathlib import Path

from devboard.agents.engines.claude_code.config_parser import ClaudeConfigParser, ClaudeConfigProject


class TestClaudeConfigParser:
    """Tests for ClaudeConfigParser.load_projects()."""

    def test_load_projects_valid_config(self, tmp_path: Path) -> None:
        config = {
            "projects": {
                "/Users/foo/myproject": {
                    "lastCost": 0.0042,
                    "lastDuration": 12345,
                    "lastLinesAdded": 10,
                    "lastLinesRemoved": 3,
                },
                "/Users/foo/otherproject": {
                    "lastCost": None,
                },
            }
        }
        config_file = tmp_path / ".claude.json"
        config_file.write_text(json.dumps(config))

        parser = ClaudeConfigParser(config_path=config_file)
        projects = parser.load_projects()

        assert len(projects) == 2

        myproject = next(p for p in projects if p.path == "/Users/foo/myproject")
        assert myproject == ClaudeConfigProject(
            path="/Users/foo/myproject",
            last_cost=0.0042,
            last_duration=12345,
            last_lines_added=10,
            last_lines_removed=3,
        )

        otherproject = next(p for p in projects if p.path == "/Users/foo/otherproject")
        assert otherproject == ClaudeConfigProject(
            path="/Users/foo/otherproject",
            last_cost=None,
            last_duration=None,
            last_lines_added=None,
            last_lines_removed=None,
        )

    def test_load_projects_file_not_found(self, tmp_path: Path) -> None:
        parser = ClaudeConfigParser(config_path=tmp_path / "nonexistent.json")
        projects = parser.load_projects()
        assert projects == []

    def test_load_projects_malformed_json(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".claude.json"
        config_file.write_text("{ invalid json }")

        parser = ClaudeConfigParser(config_path=config_file)
        projects = parser.load_projects()
        assert projects == []

    def test_load_projects_missing_projects_key(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".claude.json"
        config_file.write_text(json.dumps({"someOtherKey": {}}))

        parser = ClaudeConfigParser(config_path=config_file)
        projects = parser.load_projects()
        assert projects == []

    def test_load_projects_empty_projects(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".claude.json"
        config_file.write_text(json.dumps({"projects": {}}))

        parser = ClaudeConfigParser(config_path=config_file)
        projects = parser.load_projects()
        assert projects == []
