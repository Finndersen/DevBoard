from pydantic_ai import Tool

from devboard.integrations.codebase import CodebaseIntegration


def create_text_search_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a text search tool using ripgrep for finding specific content within files.

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def search_file_content(
        query: str,
        file_pattern: str | None = None,
        case_sensitive: bool = False,
        search_hidden: bool = False,
        path: str | None = None,
        context_before: int = 0,
        context_after: int = 0,
    ) -> str:
        """Search for text or regex patterns within file contents across the codebase (using `ripgrep`).

        Use this tool when you need to:
        - General text search needs
        - Find specific function calls, variable usages, method invocations
        - See surrounding code context for better understanding

        Examples:
        - search_file_content("def authenticate", file_pattern="*.py") - Find authentication functions
        - search_file_content("import.*pandas", file_pattern="*.py") - Find pandas imports
        - search_file_content("class.*Error", path="backend/models") - Find Error classes in backend/models
        - search_file_content("async def", file_pattern="*.py", context_before=2, context_after=5) - Find async functions with context

        Args:
            query: Text or regex pattern to search for
            file_pattern: Optional glob pattern to filter files (e.g., '*.py')
            case_sensitive: Whether search is case sensitive (default: False)
            search_hidden: Whether to search hidden/ignored files like .venv/ (default: False)
            path: Optional path to search within - can be a subdirectory (e.g., 'tests', 'src/components') or a specific file
            context_before: Number of lines to show before each match (default: 0)
            context_after: Number of lines to show after each match (default: 0)

        Returns:
            Formatted search results showing file:line:match for each occurrence,
            or a "No matches found" message if nothing was found.
        """
        result = await codebase_integration.search_file_content(
            query=query,
            file_pattern=file_pattern,
            case_sensitive=case_sensitive,
            search_hidden=search_hidden,
            path=path,
            context_before=context_before,
            context_after=context_after,
        )

        if not result:
            return f"No matches found for '{query}'"

        return "\n".join(result)

    return Tool(
        function=search_file_content,
    )


def create_file_search_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a file search tool using fd for finding files by name patterns.

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def search_files_by_name(
        pattern: str,
        extension: str | None = None,
        exclude_pattern: str | None = None,
        search_hidden: bool = False,
        path: str | None = None,
    ) -> str:
        """Search for files by name patterns across the codebase (using `fd` command, similar to `find`).

        Use this tool when you need to:
        - Find files with specific naming conventions, extensions or patterns
        - Explore project structure and understand file organization

        Examples:
        - search_files_by_name(pattern="config", extension="json") - Find JSON config files
        - search_files_by_name(pattern="test.*auth", extension="py") - Find authentication test files
        - search_files_by_name(pattern="component", exclude_pattern="*.test.*") - Find component files excluding tests
        - search_files_by_name(pattern="test_", extension="py", path="tests") - Find test files only in tests directory

        Args:
            pattern: Regex pattern to match file names/paths. Use regex syntax for complex patterns.
            extension: Optional file extension filter (e.g., 'py', 'ts', 'json').
                      Filters to only files with this extension.
            exclude_pattern: Optional pattern to exclude from results (e.g., '*.test.*', 'node_modules').
                           Useful for filtering out unwanted files.
            search_hidden: Whether to search hidden directories like .git/, .venv/.
                          Default is False (skip hidden directories).
            path: Optional subdirectory to search within (e.g., 'tests', 'src/components').
                         Limits search to files within this directory and its subdirectories.

        Returns:
            List of matching file paths relative to the codebase root,
            or a "No files found" message if no matches were found.
        """
        files = await codebase_integration.search_files(
            pattern=pattern,
            extension=extension,
            exclude_pattern=exclude_pattern,
            search_hidden=search_hidden,
            subdirectory=path,
        )

        if not files:
            return f"No files found matching pattern '{pattern}'"

        result_lines = [f"Found {len(files)} files matching '{pattern}':\n"]
        result_lines.extend(files[:100])

        if len(files) > 100:
            result_lines.append(f"\n... and {len(files) - 100} more files")

        return "\n".join(result_lines)

    return Tool(
        function=search_files_by_name,
        name="search_files_by_name",
    )


def create_code_structure_search_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a code structure search tool using ast-grep for AST-based pattern matching.

    This tool uses ast-grep to search for structural code patterns based on Abstract Syntax Trees,
    which is ideal for:
    - Finding specific function signatures, class definitions, or method patterns
    - Locating code constructs like loops, conditionals, or exception handling
    - Discovering patterns across different programming languages
    - Finding structural anti-patterns or code smells
    - Locating specific import/export patterns or decorators

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def search_code_structure(
        pattern: str,
        language: str | None = None,
        path: str | None = None,
    ) -> str:
        """Search for code structure patterns using AST-based matching (using ast-grep).

        Use this tool when you need to:
        - Find functions with specific parameter patterns or return types
        - Locate class definitions with certain inheritance or decorator patterns
        - Discover error handling patterns (try/catch blocks, exception types)
        - Find specific loop constructs or conditional statements
        - Locate patterns that span multiple lines or complex structures

        Examples:
        - search_code_structure("class $NAME(BaseException)") - Find custom exception classes
        - search_code_structure("def $FUNC($$$ARGS): $$$BODY", language="python") - Find all function definitions
        - search_code_structure("try: $$$TRY except $ERROR: $$$EXCEPT") - Find error handling patterns
        - search_code_structure("@$DECORATOR\\nclass $NAME") - Find decorated classes
        - search_code_structure("class $NAME", path="backend/models") - Find classes only in backend/models

        Args:
            pattern: AST pattern using ast-grep syntax. Use $NAME for single nodes,
                    $$$ARGS for multiple nodes, and specific syntax for language constructs.
            language: Optional language filter (e.g., 'python', 'typescript', 'rust', 'go').
                     Helps ast-grep parse files correctly and improves accuracy.
            path: Optional path to search within - can be a subdirectory (e.g., 'tests', 'src/components') or a specific file.

        Returns:
            Formatted search results showing file:line:column:match for each occurrence,
            or a "No matches found" message if no structural patterns were found.
        """
        result = await codebase_integration.search_code_structure(
            pattern=pattern,
            language=language,
            path=path,
        )

        if not result:
            return f"No code structure matches found for pattern '{pattern}'"

        return "\n".join(result)

    return Tool(
        function=search_code_structure,
        name="search_code_structure",
    )


def create_directory_tree_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a directory tree tool for visualizing tracked files in tree format.

    This tool displays the structure of git-tracked files in a hierarchical tree view,
    which is ideal for:
    - Understanding overall project structure and organization
    - Getting a quick overview of directories and files
    - Exploring unfamiliar codebases to understand layout
    - Documenting project structure or creating architectural overviews
    - Finding the location of specific modules or components

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def show_directory_tree(
        max_depth: int | None = None,
        subdirectory: str | None = None,
    ) -> str:
        """Display codebase git-tracked files in a hierarchical tree structure.

        Use this tool when you need to:
        - Understand how files and directories are organized (for entire project or specific subdirectory)
        - Explore the codebase structure before diving into specific files

        Args:
            max_depth: Maximum directory depth to display relative to subdirectory.
                      Use smaller values (1-3) for high-level overviews of large projects.
            subdirectory: Optional subdirectory to show tree for. Do not include leading/trailing slashes.

        Returns:
            Formatted tree structure showing git-tracked files and directories,
            with proper indentation and tree characters for visualization.
        """
        tree = await codebase_integration.get_directory_tree(max_depth=max_depth, subdirectory=subdirectory)
        return tree

    return Tool(
        function=show_directory_tree,
    )


def create_file_read_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a file reading tool for reading file contents with optional line ranges.

    This tool reads file contents from the codebase with optional line range specification,
    which is ideal for:
    - Reading entire files to understand implementation details
    - Reading specific sections of large files to focus on relevant parts
    - Examining function or class implementations after locating them via search
    - Reviewing configuration files, documentation, or code comments
    - Understanding code structure and implementation patterns

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def read_file(
        file_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """Read the contents of a file from the codebase, optionally reading only a specific line range.

        Examples:
        - read_file("backend/services/auth.py") - Read entire authentication service file
        - read_file("backend/models/user.py", start_line=45, end_line=75) - Read lines 45-75 of user model

        Args:
            file_path: Relative path to the file from codebase root (e.g., "backend/services/auth.py").
            start_line: Optional 1-indexed line number to start reading from (inclusive).
                       If not specified, reads from the beginning of the file.
            end_line: Optional 1-indexed line number to stop reading at (inclusive).
                     If not specified, reads to the end of the file.

        Returns:
            File contents with line numbers prepended (e.g., "  15→content"),
            or an error message if the file is not found or cannot be read.
        """
        try:
            content = await codebase_integration.read_file(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                include_line_numbers=True,
            )
            return content
        except (FileNotFoundError, ValueError) as e:
            return f"Error: {e}"

    return Tool(
        function=read_file,
        name="read_file",
    )


def create_file_write_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a file writing tool for creating new files in the codebase.

    This tool writes content to a new file in the codebase, creating parent directories
    as needed.

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def write_file(
        file_path: str,
        content: str,
        overwrite_existing: bool = False,
    ) -> str:
        """
        Create a new file with specified content, or overwrite entire content of an existing file.
        If overwrite_existing=False and the file exists, it will return an error.
        Any missing parent directories will be created.

        Examples:
        - write_file("docs/api/endpoints.md", "# API Endpoints\\n\\n...") - Create new API documentation
        - write_file("config/settings.json", "{\\"key\\": \\"value\\"}") - Create new config file
        - write_file("src/app.py", "import os...", overwrite_existing=True) - Overwrite content of existing code file

        Args:
            file_path: Relative path to the file from codebase root (e.g., "docs/new-doc.md")
            content: Full content to write to the file.
            overwrite_existing: Set to False (default) for creating a new files, or True for overwriting existing files.

        Returns:
            Success or error message.
        """
        try:
            await codebase_integration.write_file(
                file_path=file_path,
                content=content,
                overwrite_existing=overwrite_existing,
            )
            action = "overwrote" if overwrite_existing else "wrote"
            return f"Successfully {action} file: {file_path}"
        except (ValueError, OSError) as e:
            return f"Error writing file: {e}"

    return Tool(
        function=write_file,
        name="write_file",
    )


def create_file_edit_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a file editing tool for modifying existing files using find/replace.

    This tool edits existing files using find/replace patterns, which is ideal for:
    - Updating existing documentation
    - Making targeted changes to configuration
    - Modifying specific sections of files

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def edit_file(
        file_path: str,
        find: str,
        replace: str,
        replace_all: bool = False,
    ) -> str:
        """Edit an existing file using find/replace pattern.

        IMPORTANT: The 'find' text must match EXACTLY (including whitespace and line breaks).
        Use read_file first to see the exact text you need to match.

        Use this tool when you need to:
        - Update specific sections of existing documentation
        - Modify configuration values
        - Make targeted changes to existing files

        Examples:
        - edit_file("docs/README.md", "## Old Title", "## New Title") - Update a heading
        - edit_file("config.json", '"debug": false', '"debug": true') - Toggle a setting
        - edit_file("docs/guide.md", "version 1.0", "version 2.0", replace_all=True) - Update all version references

        Args:
            file_path: Relative path to the file from codebase root (e.g., "docs/guide.md").
            find: Exact text to find in the file. Must match exactly including whitespace.
            replace: Text to replace the found text with.
            replace_all: If True, replace all occurrences; if False (default), replace only the first occurrence.

        Returns:
            Success message indicating how many occurrences were replaced,
            or an error message if the operation failed.
        """
        try:
            await codebase_integration.edit_file(
                file_path=file_path,
                find=find,
                replace=replace,
                replace_all=replace_all,
            )
            mode = "all occurrences" if replace_all else "first occurrence"
            return f"Successfully edited file: {file_path} ({mode} replaced)"
        except (FileNotFoundError, ValueError, OSError) as e:
            return f"Error editing file: {e}"

    return Tool(
        function=edit_file,
        name="edit_file",
    )


def create_file_delete_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a file deletion tool for removing files from the codebase.

    This tool deletes files from the codebase.

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def delete_file(
        file_path: str,
    ) -> str:
        """Delete a file from the codebase.

        Examples:
        - delete_file("config/old-settings.json") - Remove old configuration

        Args:
            file_path: Relative path to the file from codebase root (e.g., "docs/old-doc.md").

        Returns:
            Success or error message.
        """
        try:
            await codebase_integration.delete_file(
                file_path=file_path,
            )
            return f"Successfully deleted file: {file_path}"
        except (FileNotFoundError, ValueError, OSError) as e:
            return f"Error deleting file: {e}"

    return Tool(
        function=delete_file,
        name="delete_file",
    )


def create_file_move_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a file move/rename tool for moving or renaming files in the codebase.

    This tool can both rename files in place and move them to different directories.

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def move_file(
        source_path: str,
        destination_path: str,
        overwrite_existing: bool = False,
    ) -> str:
        """Move or rename a file within the codebase.

        This tool handles both renaming (same directory) and moving (different directory).

        Use this tool when you need to:
        - Rename a file to better reflect its content
        - Move files to different directories for better organization

        Examples:
        - move_file("docs/old-name.md", "docs/new-name.md") - Rename file in same directory
        - move_file("docs/guide.md", "docs/user-guides/guide.md") - Move to subdirectory
        - move_file("README.txt", "docs/README.md") - Move and rename simultaneously
        - move_file("docs/temp.md", "docs/final.md", overwrite_existing=True) - Move with overwrite

        Args:
            source_path: Relative path to the source file from codebase root (e.g., "docs/old.md").
            destination_path: Relative path to the destination from codebase root (e.g., "docs/new.md").
                            Parent directories will be created if they don't exist.
            overwrite_existing: Set to True to allow overwriting existing files at destination.

        Returns:
            Success or error message.
        """
        try:
            await codebase_integration.move_file(
                source_path=source_path,
                destination_path=destination_path,
                overwrite_existing=overwrite_existing,
            )
            return f"Successfully moved file: {source_path} -> {destination_path}"
        except (FileNotFoundError, ValueError, OSError) as e:
            return f"Error moving file: {e}"

    return Tool(
        function=move_file,
        name="move_file",
    )
