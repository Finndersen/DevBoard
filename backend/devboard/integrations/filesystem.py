"""Filesystem integration for accessing local file system and git repository."""

import logging
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseIntegration

logger = logging.getLogger(__name__)


class FilesystemIntegration(BaseIntegration):
    """Integration for local file system and git repository access."""

    integration_type = "filesystem"

    def __init__(self):
        """Initialize filesystem integration (stateless)."""
        logger.info("Initialized Filesystem integration")

    async def test_connection(self, base_path: str | None = None) -> bool:
        """Test filesystem access by checking path."""
        path = Path(base_path or Path.cwd()).resolve()

        if not path.exists():
            logger.error(f"Path does not exist: {path}")
            return False

        if not path.is_dir():
            logger.error(f"Path is not a directory: {path}")
            return False

        # Check if it's a git repository
        git_dir = path / ".git"
        if not git_dir.exists():
            logger.warning(f"Directory is not a git repository: {path}")
            # Still return True as we can access files even without git

        return True

    def _run_git_command(self, args: list[str], base_path: str) -> str:
        """Run a git command in the specified directory."""
        result = subprocess.run(
            ["git"] + args,
            cwd=str(base_path),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    async def read_file(self, file_path: str, base_path: str) -> str:
        """Read contents of a file."""
        base = Path(base_path).resolve()
        full_path = base / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not full_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        with open(full_path, encoding="utf-8") as f:
            return f.read()

    async def list_files(
        self, directory: str = "", pattern: str | None = None, base_path: str | None = None
    ) -> list[str]:
        """List files in a directory with optional pattern matching."""
        base = Path(base_path or Path.cwd()).resolve()
        dir_path = base / directory
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")

        if pattern:
            files = [str(p.relative_to(dir_path)) for p in dir_path.rglob(pattern)]
        else:
            files = [str(p.relative_to(dir_path)) for p in dir_path.iterdir() if p.is_file()]

        return sorted(files)

    async def search_files(
        self, query: str, file_pattern: str | None = None, base_path: str | None = None
    ) -> list[dict[str, str]]:
        """Search for text within files using grep-like functionality."""
        base = Path(base_path or Path.cwd()).resolve()
        cmd_args = ["grep", "-r", "-n", query]
        if file_pattern:
            cmd_args.extend(["--include", file_pattern])
        cmd_args.append(".")

        result = subprocess.run(cmd_args, cwd=str(base), capture_output=True, text=True)

        matches = []
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if ":" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        matches.append({"file": parts[0], "line": parts[1], "content": parts[2]})

        return matches

    async def get_git_log(
        self, max_count: int = 10, file_path: str | None = None, base_path: str | None = None
    ) -> list[dict[str, str]]:
        """Get git commit history."""
        args = [
            "log",
            f"--max-count={max_count}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=iso",
        ]
        if file_path:
            args.append("--")
            args.append(file_path)

        base = Path(base_path or Path.cwd()).resolve()
        output = self._run_git_command(args, str(base))

        commits = []
        for line in output.split("\n"):
            if line.strip():
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    commits.append(
                        {
                            "hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3],
                        }
                    )

        return commits

    async def get_git_diff(
        self,
        commit1: str | None = None,
        commit2: str | None = None,
        file_path: str | None = None,
        base_path: str | None = None,
    ) -> str:
        """Get git diff between commits or working directory."""
        args = ["diff"]
        if commit1:
            if commit2:
                args.append(f"{commit1}..{commit2}")
            else:
                args.append(commit1)

        if file_path:
            args.append("--")
            args.append(file_path)

        base = Path(base_path or Path.cwd()).resolve()
        return self._run_git_command(args, str(base))

    async def get_git_branches(self, remote: bool = False, base_path: str | None = None) -> list[str]:
        """Get list of git branches."""
        args = ["branch"]
        if remote:
            args.append("-r")

        base = Path(base_path or Path.cwd()).resolve()
        output = self._run_git_command(args, str(base))
        branches = []
        for line in output.split("\n"):
            branch = line.strip()
            if branch and not branch.startswith("*"):
                branches.append(branch)
            elif branch.startswith("* "):
                branches.append(branch[2:])

        return branches

    async def get_file_tree(
        self, directory: str = "", max_depth: int | None = None, base_path: str | None = None
    ) -> dict[str, Any]:
        """Get hierarchical file tree structure."""
        base = Path(base_path or Path.cwd()).resolve()
        dir_path = base / directory
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        def build_tree(path: Path, current_depth: int = 0) -> dict[str, Any]:
            if max_depth is not None and current_depth >= max_depth:
                return {}

            tree = {}
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith(".") and item.name not in [
                        ".gitignore",
                        ".env.example",
                    ]:
                        continue

                    relative_path = str(item.relative_to(base))
                    if item.is_dir():
                        tree[item.name] = {
                            "type": "directory",
                            "path": relative_path,
                            "children": build_tree(item, current_depth + 1),
                        }
                    else:
                        tree[item.name] = {
                            "type": "file",
                            "path": relative_path,
                            "size": item.stat().st_size,
                        }
            except PermissionError:
                logger.warning(f"Permission denied accessing: {path}")

            return tree

        return build_tree(dir_path)

    async def get_file_info(self, file_path: str, base_path: str | None = None) -> dict[str, Any]:
        """Get detailed information about a file."""
        base = Path(base_path or Path.cwd()).resolve()
        full_path = base / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        stat = full_path.stat()
        info = {
            "path": file_path,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": full_path.is_file(),
            "is_dir": full_path.is_dir(),
        }

        # Add git information if available
        try:
            # Get last commit for this file
            git_log = self._run_git_command(
                ["log", "-1", "--pretty=format:%H|%an|%ad|%s", "--date=iso", "--", file_path],
                str(base),
            )
            if git_log:
                parts = git_log.split("|", 3)
                if len(parts) >= 4:
                    info["git"] = {
                        "last_commit": parts[0],
                        "last_author": parts[1],
                        "last_modified": parts[2],
                        "last_message": parts[3],
                    }
        except Exception:
            pass  # Git info is optional

        return info

    def parse_file_url(self, url: str, base_path: str | None = None) -> str | None:
        """Parse file URL to extract relative file path."""
        try:
            # Handle file:// URLs or local paths
            if url.startswith("file://"):
                file_path = url[7:]  # Remove file:// prefix
            elif url.startswith("/"):
                file_path = url
            else:
                return url  # Assume it's already a relative path

            # Convert to relative path from base path
            base = Path(base_path or Path.cwd()).resolve()
            full_path = Path(file_path).resolve()

            try:
                relative_path = full_path.relative_to(base)
                return str(relative_path)
            except ValueError:
                # Path is outside base directory
                logger.warning(f"File path outside base directory: {file_path}")
                return None

        except Exception:
            return None


def detect_git_remote_url(local_path: str) -> str | None:
    """Detect git remote URL from a local repository path.

    Returns the remote URL if found, None otherwise.
    """
    try:
        # Get remote URL (try 'origin' first, then any remote)
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(local_path),
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        # If origin doesn't exist, try to get any remote
        result = subprocess.run(["git", "remote"], cwd=str(local_path), capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and result.stdout.strip():
            first_remote = result.stdout.strip().split("\n")[0]
            result = subprocess.run(
                ["git", "remote", "get-url", first_remote],
                cwd=str(local_path),
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

        return None

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError, FileNotFoundError):
        return None
