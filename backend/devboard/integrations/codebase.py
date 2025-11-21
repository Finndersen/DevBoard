"""Filesystem integration for codebase file operations."""

from pathlib import Path

import logfire

from .base import IntegrationConnectionResult
from .shell import execute_shell_command
from .types import FileInfo


class CodebaseIntegration:
    """
    Integration for filesystem operations on codebases.
    Provides file reading, searching, and directory listing capabilities.
    """

    def __init__(self, codebase_path: str | Path):
        self._codebase_path = Path(codebase_path).resolve()

    async def validate(self) -> IntegrationConnectionResult:
        """Test filesystem access to codebase directory."""
        if not self._codebase_path.exists():
            return IntegrationConnectionResult(
                success=False, message=f"Codebase path does not exist: {self._codebase_path}"
            )

        if not self._codebase_path.is_dir():
            return IntegrationConnectionResult(
                success=False, message=f"Codebase path is not a directory: {self._codebase_path}"
            )

        return IntegrationConnectionResult(success=True, message=f"Directory accessible at: {self._codebase_path}")

    async def read_file(
        self,
        file_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        include_line_numbers: bool = False,
    ) -> str:
        """Read contents of a file, optionally reading only a specific line range.

        Args:
            file_path: Relative path to file from codebase root
            start_line: Optional 1-indexed line number to start reading from (inclusive)
            end_line: Optional 1-indexed line number to stop reading at (inclusive)
            include_line_numbers: Whether to prepend line numbers to output (default: False)

        Returns:
            File contents as string. If include_line_numbers is True, line numbers
            are prepended (e.g., "  15→content")

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the path is not a file or if line range is invalid
        """
        full_path = self._codebase_path / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not full_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        # Validate line range parameters
        if start_line is not None and start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {start_line}")
        if end_line is not None and end_line < 1:
            raise ValueError(f"end_line must be >= 1, got {end_line}")
        if start_line is not None and end_line is not None and start_line > end_line:
            raise ValueError(f"start_line ({start_line}) must be <= end_line ({end_line})")

        with open(full_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Determine the range to read
        total_lines = len(lines)
        if start_line is None:
            start_idx = 0
        else:
            start_idx = max(0, start_line - 1)

        if end_line is None:
            end_idx = total_lines
        else:
            end_idx = min(end_line, total_lines)

        # Format output with optional line numbers
        result_lines = []
        for i in range(start_idx, end_idx):
            line_content = lines[i].rstrip("\n")
            if include_line_numbers:
                line_num = i + 1
                result_lines.append(f"{line_num:>5}→{line_content}")
            else:
                result_lines.append(line_content)

        return "\n".join(result_lines)

    async def list_directory_contents(
        self, directory: str = "", pattern: str | None = None, include_directories: bool = False
    ) -> list[str]:
        """List files and optionally directories in a directory with optional pattern matching.

        Args:
            directory: Relative directory path from codebase root
            pattern: Optional glob pattern for filtering (uses recursive rglob)
            include_directories: Whether to include directories in results (default: False)

        Returns:
            List of relative paths. Directories are marked with trailing '/' when included.
        """
        dir_path = self._codebase_path / directory
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")

        entries = []
        pattern = pattern or "*"
        # Use rglob for recursive pattern matching
        for p in dir_path.rglob(pattern):
            if p.is_file():
                entries.append(str(p.relative_to(dir_path)))
            elif p.is_dir() and include_directories:
                entries.append(str(p.relative_to(dir_path)) + "/")

        return sorted(entries)

    async def search_file_content(
        self,
        query: str,
        file_pattern: str | None = None,
        case_sensitive: bool = False,
        search_hidden: bool = False,
        path: str | None = None,
        context_before: int = 0,
        context_after: int = 0,
    ) -> list[str]:
        """Search for text within files using ripgrep.

        Args:
            query: Text or regex pattern to search for
            file_pattern: Optional glob pattern to filter files (e.g., '*.py')
            case_sensitive: Whether search is case sensitive (default: False)
            search_hidden: Whether to search hidden/ignored files like .venv/ (default: False)
            path: Optional path to search within - can be a subdirectory (e.g., 'tests', 'src/components') or a specific file
            context_before: Number of lines to show before each match (default: 0)
            context_after: Number of lines to show after each match (default: 0)

        Returns:
            List of matching lines from ripgrep output
        TODO: Output appears to repeat the file path multiple times, e.g.:
        backend/devboard/services/workflow_action_service.py-8-
        backend/devboard/services/workflow_action_service.py-9-
        backend/devboard/services/workflow_action_service.py:10:class PromptActionNotFoundError(Exception):
        backend/devboard/services/workflow_action_service.py-11-    \"\"\"Raised when a requested prompt action key does not exist.\"\"\"
        backend/devboard/services/workflow_action_service.py-12-
        backend/devboard/services/workflow_action_service.py-13-    pass
        backend/devboard/services/workflow_action_service.py-14-
        backend/devboard/services/workflow_action_service.py-15-
        backend/devboard/services/workflow_action_service.py:16:class PromptActionService:
        backend/devboard/services/workflow_action_service.py-17-    \"\"\"Service for managing and executing prompt actions.
        backend/devboard/services/workflow_action_service.py-18-
        backend/devboard/services/workflow_action_service.py-19-    Prompt actions are reusable, named operations that send predefined prompts
        backend/devboard/services/workflow_action_service.py-20-    to agent conversations. This service handles action lookup and execution.
        backend/devboard/services/workflow_action_service.py-21-    \"\"\"
        --
        backend/devboard/agents/base.py-11-
        backend/devboard/agents/base.py-12-@dataclass(frozen=True)
        backend/devboard/agents/base.py:13:class PromptAction:
        backend/devboard/agents/base.py-14-    \"\"\"A reusable prompt action that can be triggered in conversations.
        backend/devboard/agents/base.py-15-
        backend/devboard/agents/base.py-16-    Attributes:
        backend/devboard/agents/base.py-17-        key: Unique identifier for the action (e.g., \"task.create_implementation_plan\")
        backend/devboard/agents/base.py-18-        prompt_template: The prompt text to send to the agent
        """
        cmd = ["rg", "--line-number"]

        if not case_sensitive:
            cmd.append("--ignore-case")

        if search_hidden:
            cmd.append("--no-ignore")

        if file_pattern:
            cmd.extend(["--glob", file_pattern])

        if context_before > 0:
            cmd.extend(["-B", str(context_before)])

        if context_after > 0:
            cmd.extend(["-A", str(context_after)])

        cmd.append(query)

        # Add path if specified (can be subdirectory or specific file)
        if path:
            # Remove trailing slash for consistency
            path = path.rstrip("/")
            cmd.append(path)

        result = await execute_shell_command(
            cmd,
            working_dir=self._codebase_path,
            timeout=30.0,
            raise_on_error=False,
        )

        if result.success and result.stdout:
            return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return []

    async def search_files(
        self,
        pattern: str,
        extension: str | None = None,
        exclude_pattern: str | None = None,
        search_hidden: bool = False,
        subdirectory: str | None = None,
    ) -> list[str]:
        """Search for files by name pattern using fd.

        Args:
            pattern: Regex pattern to match file names
            extension: Optional file extension filter (e.g., 'py', 'ts')
            exclude_pattern: Optional pattern to exclude from results
            search_hidden: Whether to search hidden directories (default: False)
            subdirectory: Optional subdirectory to search within (e.g., 'tests', 'src/components')

        Returns:
            List of relative file paths matching the pattern (paths are relative to codebase root)
        """
        cmd = ["fd", "--type", "f"]

        if search_hidden:
            cmd.append("--hidden")

        if extension:
            cmd.extend(["--extension", extension])

        if exclude_pattern:
            cmd.extend(["--exclude", exclude_pattern])

        cmd.append(pattern)

        # Add subdirectory path if specified
        if subdirectory:
            # Remove trailing slash for consistency
            subdirectory = subdirectory.rstrip("/")
            cmd.append(subdirectory)

        result = await execute_shell_command(
            cmd,
            working_dir=self._codebase_path,
            timeout=30.0,
            raise_on_error=False,
        )

        if result.success and result.stdout:
            files = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            return sorted(files)

        return []

    async def search_code_structure(
        self,
        pattern: str,
        language: str | None = None,
        path: str | None = None,
    ) -> list[str]:
        """Search for code structure patterns using ast-grep.

        Args:
            pattern: AST pattern to search (e.g., 'class $NAME', 'def $FUNC($$$ARGS)')
            language: Optional language filter (e.g., 'python', 'typescript', 'rust')
            path: Optional path to search within - can be a subdirectory (e.g., 'tests', 'src/components') or a specific file

        Returns:
            List of matching lines from ast-grep output

        TODO: Output appears to repeat the file path multiple times, e.g.:
        Search: "class TaskStatus(StrEnum):
        $$$"
        Returns:
        backend/devboard/db/models/task.py:19:class TaskStatus(StrEnum):
        backend/devboard/db/models/task.py:20:    ""Enumeration of possible task statuses.""
        backend/devboard/db/models/task.py:21:
        backend/devboard/db/models/task.py:22:    DEFINING = "defining"
        backend/devboard/db/models/task.py:23:    PLANNING = "planning"
        backend/devboard/db/models/task.py:24:    IMPLEMENTING = "implementing"
        backend/devboard/db/models/task.py:25:    REVIEWING = "reviewing"
        backend/devboard/db/models/task.py:26:    COMPLETE = "complete"
        """
        cmd = ["ast-grep", "--pattern", pattern]

        if language:
            cmd.extend(["--lang", language])

        # Add path if specified (can be subdirectory or specific file)
        if path:
            # Remove trailing slash for consistency
            path = path.rstrip("/")
            cmd.append(path)

        result = await execute_shell_command(
            cmd,
            working_dir=self._codebase_path,
            timeout=30.0,
            raise_on_error=False,
        )

        if result.success and result.stdout:
            return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return []

    async def get_directory_tree(self, max_depth: int | None = None, subdirectory: str | None = None) -> str:
        """Get git-tracked file tree structure using piped git ls-files | tree command.

        Args:
            max_depth: Maximum depth to display relative to subdirectory (None for unlimited)
            subdirectory: Optional subdirectory to explore (e.g., 'src/', 'tests/')

        Returns:
            Tree structure as formatted string
        """
        # Build the git ls-files command with optional subdirectory filter
        git_cmd = "git ls-files"
        if subdirectory:
            # Remove trailing slash if present for consistency
            subdirectory = subdirectory.rstrip("/")
            git_cmd += f" '{subdirectory}/'"

        # Calculate actual tree depth accounting for subdirectory depth
        tree_args = "tree --fromfile -F"
        if max_depth is not None:
            actual_depth = max_depth
            if subdirectory:
                # Add the depth of the subdirectory path to max_depth
                subdirectory_depth = len(subdirectory.split("/"))
                actual_depth = max_depth + subdirectory_depth
            tree_args += f" -L {actual_depth}"

        piped_cmd = f"{git_cmd} | {tree_args}"

        result = await execute_shell_command(
            [piped_cmd],
            working_dir=self._codebase_path,
            timeout=30.0,
            raise_on_error=False,
        )

        if result.success:
            return result.stdout
        else:
            return f"Error generating file tree: {result.stderr}"

    async def get_file_info(self, file_path: str) -> FileInfo:
        """Get detailed information about a file.

        Args:
            file_path: Relative path to file from codebase root

        Returns:
            FileInfo object with file metadata

        Raises:
            FileNotFoundError: If the file does not exist
        """
        full_path = self._codebase_path / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        stat = full_path.stat()
        return FileInfo(
            path=file_path,
            size=stat.st_size,
            modified=stat.st_mtime,
            is_file=full_path.is_file(),
            is_dir=full_path.is_dir(),
        )

    def parse_file_url(self, url: str) -> str | None:
        """Parse file URL to extract relative file path.

        Args:
            url: File URL or path

        Returns:
            Relative path from codebase root, or None if invalid
        """
        if url.startswith("file://"):
            file_path = url[7:]
        elif url.startswith("/"):
            file_path = url
        else:
            return url

        full_path = Path(file_path).resolve()

        try:
            relative_path = full_path.relative_to(self._codebase_path)
            return str(relative_path)
        except ValueError:
            logfire.warning(f"File path outside codebase directory: {file_path}")
            return None
