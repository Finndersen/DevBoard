"""Claude Code session migration — moves session files when working directory changes."""

import json
import platform
import shutil
from pathlib import Path

import logfire

from devboard.agents.engines.claude_code.session.file_locator import find_session_file
from devboard.integrations.shell import execute_shell_command


class ClaudeCodeSessionMigrator:
    """Migrates Claude Code session files to a new working directory."""

    def __init__(self):
        self.claude_projects_dir = Path.home() / ".claude" / "projects"

    @staticmethod
    def encode_path_for_claude_projects(path: str) -> str:
        """Encode a filesystem path to Claude's project directory format."""
        return "-" + path.lstrip("/").replace("/", "-").replace(".", "-")

    def _extract_cwd_from_session_file(self, session_file: Path) -> str:
        """Extract the working directory from a session file."""
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

    async def migrate_session_to_directory(self, session_id: str, new_working_dir: str) -> Path | None:
        """Migrate a session file to a new working directory."""
        old_session_file = find_session_file(session_id, self.claude_projects_dir)
        old_project_dir = old_session_file.parent

        new_encoded_path = self.encode_path_for_claude_projects(new_working_dir)
        new_project_dir = self.claude_projects_dir / new_encoded_path

        if old_project_dir == new_project_dir:
            logfire.debug(f"Session {session_id} already in correct location: {new_working_dir}")
            return None

        new_project_dir.mkdir(parents=True, exist_ok=True)

        new_session_file = new_project_dir / old_session_file.name
        shutil.move(str(old_session_file), str(new_session_file))
        logfire.info(f"Moved session file from {old_session_file} to {new_session_file}")

        old_session_dir = old_project_dir / session_id
        if old_session_dir.exists() and old_session_dir.is_dir():
            new_session_dir = new_project_dir / session_id
            shutil.move(str(old_session_dir), str(new_session_dir))
            logfire.info(f"Moved session directory from {old_session_dir} to {new_session_dir}")

        old_working_dir = self._extract_cwd_from_session_file(new_session_file)
        if platform.system() == "Darwin":
            sed_cmd = ["sed", "-i", "", f"s|{old_working_dir}|{new_working_dir}|g", str(new_session_file)]
        else:
            sed_cmd = ["sed", "-i", f"s|{old_working_dir}|{new_working_dir}|g", str(new_session_file)]

        await execute_shell_command(sed_cmd)
        logfire.info(f"Replaced paths in session file: {old_working_dir} → {new_working_dir}")

        return new_session_file
