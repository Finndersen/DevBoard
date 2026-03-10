"""Parser for ~/.claude.json configuration file."""

import json
from dataclasses import dataclass
from pathlib import Path

import logfire


@dataclass
class ClaudeConfigProject:
    """Structured representation of a project entry from ~/.claude.json."""

    path: str
    last_cost: float | None
    last_duration: int | None
    last_lines_added: int | None
    last_lines_removed: int | None


class ClaudeConfigParser:
    """Parser for the Claude Code global config at ~/.claude.json."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or Path.home() / ".claude.json"

    def load_projects(self) -> list[ClaudeConfigProject]:
        """Read and parse the ~/.claude.json file, returning all project entries.

        Returns empty list if file not found, malformed, or missing 'projects' key.
        """
        try:
            with self.config_path.open("r") as f:
                data = json.load(f)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as e:
            logfire.warning(f"Malformed ~/.claude.json: {e}")
            return []

        projects = data.get("projects")
        if not isinstance(projects, dict):
            return []

        result: list[ClaudeConfigProject] = []
        for path, entry in projects.items():
            if not isinstance(entry, dict):
                continue
            result.append(
                ClaudeConfigProject(
                    path=path,
                    last_cost=entry.get("lastCost"),
                    last_duration=entry.get("lastDuration"),
                    last_lines_added=entry.get("lastLinesAdded"),
                    last_lines_removed=entry.get("lastLinesRemoved"),
                )
            )

        return result
