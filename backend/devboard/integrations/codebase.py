"""Codebase integration for accessing local file system and git repository."""

import logging
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseIntegration, IntegrationError

logger = logging.getLogger(__name__)


class CodebaseIntegration(BaseIntegration):
    """Integration for local file system and git repository access."""
    
    integration_type = "codebase"

    def __init__(self, repo_path: str):
        """Initialize with repository path."""
        self.repo_path = repo_path
        logger.info(f"Initialized Codebase integration for {repo_path}")

    async def test_connection(self) -> bool:
        """Test codebase access by checking repository path."""
        try:
            repo_path = Path(self.repo_path)
            if not repo_path.exists():
                logger.error(f"Repository path does not exist: {repo_path}")
                return False

            if not repo_path.is_dir():
                logger.error(f"Repository path is not a directory: {repo_path}")
                return False

            # Check if it's a git repository
            git_dir = repo_path / ".git"
            if not git_dir.exists():
                logger.warning(f"Directory is not a git repository: {repo_path}")
                # Still return True as we can access files even without git

            return True
        except Exception as e:
            logger.error(f"Codebase connection test failed: {e}")
            return False

    def _run_git_command(self, args: list[str]) -> str:
        """Run a git command in the repository directory."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {e.stderr}")
            raise

    async def read_file(self, file_path: str) -> str:
        """Read contents of a file."""
        try:
            full_path = Path(self.repo_path) / file_path
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            if not full_path.is_file():
                raise ValueError(f"Path is not a file: {file_path}")

            with open(full_path, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise
        except ValueError:
            raise

    async def list_files(self, directory: str = "", pattern: str | None = None) -> list[str]:
        """List files in a directory with optional pattern matching."""
        try:
            dir_path = Path(self.repo_path) / directory
            if not dir_path.exists():
                raise FileNotFoundError(f"Directory not found: {directory}")

            if not dir_path.is_dir():
                raise ValueError(f"Path is not a directory: {directory}")

            files = []
            if pattern:
                files = [str(p.relative_to(dir_path)) for p in dir_path.rglob(pattern)]
            else:
                files = [str(p.relative_to(dir_path)) for p in dir_path.iterdir() if p.is_file()]

            return sorted(files)
        except FileNotFoundError:
            raise
        except ValueError:
            raise

    async def search_files(
        self, query: str, file_pattern: str | None = None
    ) -> list[dict[str, str]]:
        """Search for text within files using grep-like functionality."""
        try:
            cmd_args = ["grep", "-r", "-n", query]
            if file_pattern:
                cmd_args.extend(["--include", file_pattern])
            cmd_args.append(".")

            result = subprocess.run(
                cmd_args, cwd=self.repo_path, capture_output=True, text=True
            )

            matches = []
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if ":" in line:
                        parts = line.split(":", 2)
                        if len(parts) >= 3:
                            matches.append(
                                {"file": parts[0], "line": parts[1], "content": parts[2]}
                            )

            return matches

    async def get_git_log(
        self, max_count: int = 10, file_path: str | None = None
    ) -> list[dict[str, str]]:
        """Get git commit history."""
        try:
            args = [
                "log",
                f"--max-count={max_count}",
                "--pretty=format:%H|%an|%ad|%s",
                "--date=iso",
            ]
            if file_path:
                args.append("--")
                args.append(file_path)

            output = self._run_git_command(args)

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
    ) -> str:
        """Get git diff between commits or working directory."""
        try:
            args = ["diff"]
            if commit1:
                if commit2:
                    args.append(f"{commit1}..{commit2}")
                else:
                    args.append(commit1)

            if file_path:
                args.append("--")
                args.append(file_path)

            return self._run_git_command(args)

    async def get_git_branches(self, remote: bool = False) -> list[str]:
        """Get list of git branches."""
        try:
            args = ["branch"]
            if remote:
                args.append("-r")

            output = self._run_git_command(args)
            branches = []
            for line in output.split("\n"):
                branch = line.strip()
                if branch and not branch.startswith("*"):
                    branches.append(branch)
                elif branch.startswith("* "):
                    branches.append(branch[2:])

            return branches

    async def get_file_tree(
        self, directory: str = "", max_depth: int | None = None
    ) -> dict[str, Any]:
        """Get hierarchical file tree structure."""
        try:
            dir_path = Path(self.repo_path) / directory
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

                        relative_path = str(item.relative_to(Path(self.repo_path)))
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

    async def get_file_info(self, file_path: str) -> dict[str, Any]:
        """Get detailed information about a file."""
        try:
            full_path = Path(self.repo_path) / file_path
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
                    ["log", "-1", "--pretty=format:%H|%an|%ad|%s", "--date=iso", "--", file_path]
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

    def parse_file_url(self, url: str) -> str | None:
        """Parse file URL to extract relative file path."""
        try:
            # Handle file:// URLs or local paths
            if url.startswith("file://"):
                file_path = url[7:]  # Remove file:// prefix
            elif url.startswith("/"):
                file_path = url
            else:
                return url  # Assume it's already a relative path

            # Convert to relative path from repo root
            repo_path = Path(self.repo_path).resolve()
            full_path = Path(file_path).resolve()

            try:
                relative_path = full_path.relative_to(repo_path)
                return str(relative_path)
            except ValueError:
                # Path is outside repository
                logger.warning(f"File path outside repository: {file_path}")
                return None

        except Exception:
            return None

    async def investigate_codebase(self, query: str, context: str = "") -> str:
        """High-level codebase investigation using Gemini CLI agent.
        
        Args:
            query: The investigation question or task
            context: Additional context about what to focus on
            
        Returns:
            AI-generated analysis and findings
        """
        try:
            full_prompt = f"""
You are analyzing a codebase located at: {self.repo_path}

Investigation Query: {query}

Additional Context: {context}

Please analyze the codebase structure, patterns, and implementation to answer the query.
Focus on providing specific, actionable insights about the code organization, architecture, and relevant implementation details.
"""

            result = subprocess.run(
                ["gemini-cli", "prompt", full_prompt.strip()],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                logger.info(f"Codebase investigation completed: {query}")
                return result.stdout.strip()
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"Gemini CLI failed: {error_msg}")
                raise IntegrationError(f"Gemini CLI error: {error_msg}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"Codebase investigation timed out for '{query}'")
            raise IntegrationError("Codebase investigation timed out after 60 seconds")
        except FileNotFoundError:
            logger.error("Gemini CLI not found - ensure gemini-cli is installed and in PATH")
            raise IntegrationError("Gemini CLI not installed - install from https://github.com/eliben/gemini-cli")
