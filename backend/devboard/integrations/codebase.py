"""Codebase integration for exploring and analyzing code repositories."""

import subprocess
from pathlib import Path
from typing import Any

import logfire

from .base import IntegrationConnectionResult
from .shell import execute_shell_command


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

    def _validate_file_path(
        self,
        file_path: str,
        must_exist: bool = False,
        must_be_file: bool = False,
    ) -> Path:
        """Validate and resolve a file path within the codebase.

        Args:
            file_path: Relative path to file from codebase root
            must_exist: If True, raises FileNotFoundError if path doesn't exist
            must_be_file: If True, raises ValueError if path is not a file

        Returns:
            Resolved absolute Path object

        Raises:
            ValueError: If path is outside codebase or not a file (when must_be_file=True)
            FileNotFoundError: If path doesn't exist (when must_exist=True)
        """
        full_path = self.codebase_path / file_path

        # Ensure path is within codebase directory
        try:
            full_path.resolve().relative_to(self.codebase_path)
        except ValueError:
            raise ValueError(f"Path is outside codebase directory: {file_path}")

        if must_exist and not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if must_be_file and not full_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        return full_path

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
        full_path = self.codebase_path / file_path
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
        dir_path = self.codebase_path / directory
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
        """
        cmd = ["rg", "--line-number", "--heading"]

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
            working_dir=self.codebase_path,
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
            working_dir=self.codebase_path,
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
            List of matching lines from ast-grep output. File paths are shown as headings.
        """
        cmd = ["ast-grep", "--pattern", pattern, "--heading=always"]

        if language:
            cmd.extend(["--lang", language])

        # Add path if specified (can be subdirectory or specific file)
        if path:
            # Remove trailing slash for consistency
            path = path.rstrip("/")
            cmd.append(path)

        result = await execute_shell_command(
            cmd,
            working_dir=self.codebase_path,
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
            working_dir=self.codebase_path,
            timeout=30.0,
            raise_on_error=False,
        )

        if result.success:
            return result.stdout
        else:
            return f"Error generating file tree: {result.stderr}"

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

        git_log = self._run_git_command(["log", "-1", "--pretty=format:%H|%an|%ad|%s", "--date=iso", "--", file_path])
        if git_log:
            parts = git_log.split("|", 3)
            if len(parts) >= 4:
                info["git"] = {
                    "last_commit": parts[0],
                    "last_author": parts[1],
                    "last_modified": parts[2],
                    "last_message": parts[3],
                }

        return info

    async def write_file(self, file_path: str, content: str, overwrite_existing: bool = False) -> None:
        """Write content to a file, creating it if it doesn't exist.

        Args:
            file_path: Relative path to file from codebase root
            content: Content to write to the file
            overwrite_existing: If False (default), raises error if file already exists.
                              If True, allows overwriting existing files.

        Raises:
            ValueError: If the path is invalid, outside codebase, or file already exists when overwrite_existing=False
            OSError: If file cannot be written
        """
        # Validate path is within codebase (but don't require it to exist yet)
        full_path = self._validate_file_path(file_path)

        # Check if file exists
        file_existed = full_path.exists()

        # Raise error if file exists and overwrite_existing is False
        if not overwrite_existing and file_existed:
            raise ValueError(f"File already exists: {file_path}. Use overwrite_existing=True to overwrite.")

        # Create parent directories if they don't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content to file
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        action = "overwritten" if file_existed else "written"
        logfire.info(f"File {action}: {file_path}")

    async def delete_file(self, file_path: str) -> None:
        """Delete a file from the codebase.

        Args:
            file_path: Relative path to file from codebase root

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the path is not a file or outside codebase
            OSError: If file cannot be deleted
        """
        # Validate path, ensure it exists and is a file
        full_path = self._validate_file_path(file_path, must_exist=True, must_be_file=True)

        # Delete the file
        full_path.unlink()

        logfire.info(f"File deleted: {file_path}")

    async def move_file(self, source_path: str, destination_path: str, overwrite_existing: bool = False) -> None:
        """Move or rename a file within the codebase.

        This operation can be used to:
        - Rename a file in the same directory
        - Move a file to a different directory
        - Move and rename a file simultaneously

        Args:
            source_path: Relative path to source file from codebase root
            destination_path: Relative path to destination from codebase root
            overwrite_existing: If False (default), raises error if destination already exists.
                              If True, allows overwriting existing files at destination.

        Raises:
            FileNotFoundError: If the source file does not exist
            ValueError: If source is not a file, paths are outside codebase, or destination exists when overwrite_existing=False
            OSError: If file cannot be moved
        """
        # Validate source path (must exist and be a file)
        source_full = self._validate_file_path(source_path, must_exist=True, must_be_file=True)

        # Validate destination path (just check it's within codebase, don't require it to exist)
        dest_full = self._validate_file_path(destination_path)

        # Check if destination exists
        if dest_full.exists() and not overwrite_existing:
            raise ValueError(
                f"Destination already exists: {destination_path}. Use overwrite_existing=True to overwrite."
            )

        # Create parent directories for destination if needed
        dest_full.parent.mkdir(parents=True, exist_ok=True)

        # Move/rename the file
        source_full.rename(dest_full)

        logfire.info(f"File moved: {source_path} -> {destination_path}")

    async def edit_file(self, file_path: str, find: str, replace: str, replace_all: bool = False) -> None:
        """Edit a file using find/replace pattern.

        Args:
            file_path: Relative path to file from codebase root
            find: Text to find in the file (must match exactly)
            replace: Text to replace with
            replace_all: If True, replace all occurrences; if False, replace only first occurrence

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the find text is not found in the file or if path is invalid
            OSError: If file cannot be read or written
        """
        # Validate path, ensure it exists and is a file
        full_path = self._validate_file_path(file_path, must_exist=True, must_be_file=True)

        # Read file content
        with open(full_path, encoding="utf-8") as f:
            content = f.read()

        # Check if find text exists
        if find not in content:
            raise ValueError(f"Find text not found in file: '{find}'")

        # Perform replacement
        if replace_all:
            new_content = content.replace(find, replace)
            occurrences = content.count(find)
        else:
            new_content = content.replace(find, replace, 1)
            occurrences = 1

        # Write updated content
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        logfire.info(f"File edited: {file_path} ({occurrences} occurrence(s) replaced)")

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
            relative_path = full_path.relative_to(self.codebase_path)
            return str(relative_path)
        except ValueError:
            logfire.warning(f"File path outside codebase directory: {file_path}")
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
