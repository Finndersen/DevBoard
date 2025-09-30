"""Codebase integration for exploring and analyzing code repositories."""

import logging
import subprocess
from pathlib import Path
from typing import Any

from .base import IntegrationConnectionResult
from .shell import execute_shell_command

logger = logging.getLogger(__name__)


class CodebaseIntegration:
    """
    Integration for codebase exploration and analysis. Follows different pattern to other "external" integrations
    - Filesystem access for reading and listing files
    - File and content search
    - Git operations
    """

    def __init__(self, codebase_path: str | Path):
        """Initialize codebase integration.

        Args:
            codebase_path: Path to the git repository root
        """
        self.codebase_path = Path(codebase_path).resolve()

    async def validate(self) -> IntegrationConnectionResult:
        """Test codebase access and git repository detection."""
        if not self.codebase_path.exists():
            return IntegrationConnectionResult(
                success=False, message=f"Codebase path does not exist: {self.codebase_path}"
            )

        if not self.codebase_path.is_dir():
            return IntegrationConnectionResult(
                success=False, message=f"Codebase path is not a directory: {self.codebase_path}"
            )

        git_dir = self.codebase_path / ".git"
        if not git_dir.exists():
            return IntegrationConnectionResult(
                success=True, message=f"Directory accessible but not a git repository: {self.codebase_path}"
            )

        return IntegrationConnectionResult(success=True, message=f"Git repository accessible at: {self.codebase_path}")

    def _run_git_command(self, args: list[str]) -> str:
        """Run a git command in the codebase directory."""
        result = subprocess.run(
            ["git"] + args,
            cwd=str(self.codebase_path),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    async def read_file(self, file_path: str) -> str:
        """Read contents of a file.

        Args:
            file_path: Relative path to file from codebase root

        Returns:
            File contents as string
        """
        full_path = self.codebase_path / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not full_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        with open(full_path, encoding="utf-8") as f:
            return f.read()

    async def list_files(self, directory: str = "", pattern: str | None = None) -> list[str]:
        """List files in a directory with optional pattern matching.

        Args:
            directory: Relative directory path from codebase root
            pattern: Optional glob pattern for filtering

        Returns:
            List of relative file paths
        """
        dir_path = self.codebase_path / directory
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")

        if pattern:
            files = [str(p.relative_to(dir_path)) for p in dir_path.rglob(pattern)]
        else:
            files = [str(p.relative_to(dir_path)) for p in dir_path.iterdir() if p.is_file()]

        return sorted(files)

    async def search_file_content(
        self,
        query: str,
        file_pattern: str | None = None,
        case_sensitive: bool = False,
        search_hidden: bool = False,
    ) -> list[str]:
        """Search for text within files using ripgrep.

        Args:
            query: Text or regex pattern to search for
            file_pattern: Optional glob pattern to filter files (e.g., '*.py')
            case_sensitive: Whether search is case sensitive (default: False)
            search_hidden: Whether to search hidden/ignored files like .venv/ (default: False)

        Returns:
            List of matching lines from ripgrep output
        """
        cmd = ["rg", "--line-number"]

        if not case_sensitive:
            cmd.append("--ignore-case")

        if search_hidden:
            cmd.append("--no-ignore")

        if file_pattern:
            cmd.extend(["--glob", file_pattern])

        cmd.append(query)

        try:
            result = await execute_shell_command(
                cmd,
                working_dir=self.codebase_path,
                timeout=30.0,
                raise_on_error=False,
            )

            if result.success and result.stdout:
                return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            return []

        except Exception as e:
            logger.error(f"Error searching file content with ripgrep: {e}")
            return []

    async def search_files(
        self,
        pattern: str,
        extension: str | None = None,
        exclude_pattern: str | None = None,
        search_hidden: bool = False,
    ) -> list[str]:
        """Search for files by name pattern using fd.

        Args:
            pattern: Regex pattern to match file names
            extension: Optional file extension filter (e.g., 'py', 'ts')
            exclude_pattern: Optional pattern to exclude from results
            search_hidden: Whether to search hidden directories (default: False)

        Returns:
            List of relative file paths matching the pattern
        """
        cmd = ["fd", "--type", "f"]

        if search_hidden:
            cmd.append("--hidden")

        if extension:
            cmd.extend(["--extension", extension])

        if exclude_pattern:
            cmd.extend(["--exclude", exclude_pattern])

        cmd.append(pattern)

        try:
            result = await execute_shell_command(
                cmd,
                working_dir=self.codebase_path,
                timeout=30.0,
                raise_on_error=False,
            )

            if result.success and result.stdout:
                files = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
                return sorted(files)

            return []

        except Exception as e:
            logger.error(f"Error searching files with fd: {e}")
            return []

    async def search_code_structure(self, pattern: str, language: str | None = None) -> list[str]:
        """Search for code structure patterns using ast-grep.

        Args:
            pattern: AST pattern to search (e.g., 'class $NAME', 'def $FUNC($$$ARGS)')
            language: Optional language filter (e.g., 'python', 'typescript', 'rust')

        Returns:
            List of matching lines from ast-grep output
        """
        cmd = ["ast-grep", "--pattern", pattern]

        if language:
            cmd.extend(["--lang", language])

        try:
            result = await execute_shell_command(
                cmd,
                working_dir=self.codebase_path,
                timeout=30.0,
                raise_on_error=False,
            )

            if result.success and result.stdout:
                return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            return []

        except Exception as e:
            logger.error(f"Error searching code structure with ast-grep: {e}")
            return []

    async def get_directory_tree(self, max_depth: int | None = None) -> str:
        """Get git-tracked file tree structure using piped git ls-files | tree command.

        Args:
            max_depth: Maximum depth to display (None for unlimited)

        Returns:
            Tree structure as formatted string
        """
        # Build the piped command: git ls-files | tree --fromfile
        tree_args = "tree --fromfile -F"
        if max_depth is not None:
            tree_args += f" -L {max_depth}"

        piped_cmd = f"git ls-files | {tree_args}"

        try:
            result = await execute_shell_command(
                [piped_cmd],
                working_dir=self.codebase_path,
                timeout=30.0,
                raise_on_error=False,
            )

            if result.success:
                return result.stdout
            else:
                return f"Error generating file tree: {result.stderr}"

        except Exception as e:
            logger.error(f"Error getting file tree: {e}")
            return f"Error: {str(e)}"

    async def get_git_log(self, max_count: int = 10, file_path: str | None = None) -> list[dict[str, str]]:
        """Get git commit history.

        Args:
            max_count: Maximum number of commits to retrieve
            file_path: Optional file path to get history for specific file

        Returns:
            List of commit dictionaries with hash, author, date, message
        """
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
        """Get git diff between commits or working directory.

        Args:
            commit1: First commit hash/reference
            commit2: Second commit hash/reference (optional)
            file_path: Optional file path to get diff for specific file

        Returns:
            Diff output as string
        """
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
        """Get list of git branches.

        Args:
            remote: Whether to list remote branches

        Returns:
            List of branch names
        """
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

    async def get_file_info(self, file_path: str) -> dict[str, Any]:
        """Get detailed information about a file.

        Args:
            file_path: Relative path to file from codebase root

        Returns:
            Dictionary with file metadata and git information
        """
        full_path = self.codebase_path / file_path
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

        try:
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
            pass

        return info

    def parse_file_url(self, url: str) -> str | None:
        """Parse file URL to extract relative file path.

        Args:
            url: File URL or path

        Returns:
            Relative path from codebase root, or None if invalid
        """
        try:
            if url.startswith("file://"):
                file_path = url[7:]
            elif url.startswith("/"):
                file_path = url
            else:
                return url

            full_path = Path(file_path).resolve()

            try:
                relative_path = full_path.relative_to(self.codebase_path)
                return str(relative_path)
            except ValueError:
                logger.warning(f"File path outside codebase directory: {file_path}")
                return None

        except Exception:
            return None


def detect_git_remote_url(local_path: str) -> str | None:
    """Detect git remote URL from a local repository path.

    Args:
        local_path: Path to local git repository

    Returns:
        Remote URL if found, None otherwise
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(local_path),
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

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
