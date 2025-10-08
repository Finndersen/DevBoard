from pydantic_ai import ApprovalRequired, RunContext, Tool

from devboard.agents.deps import BaseDeps
from devboard.api.schemas import DocumentEdit
from devboard.db.models.document import Document
from devboard.db.repositories.document import DocumentRepository
from devboard.integrations.codebase import CodebaseIntegration
from devboard.services.document_editor import DocumentEditorService


def create_document_edit_tool(document: Document, document_repo: DocumentRepository) -> Tool:
    """Create a document editing tool.
    First, the edits are validated to ensure they can be applied. If validation passes,
    the tool will request approval before applying the edits.

    Args:
        document: Document model to edit
        document_repo: Repository for document operations
    """

    def edit_document_tool(ctx: RunContext[BaseDeps], edits: list[DocumentEdit], reasoning: str = "") -> str:
        """Edit document with the provided edits.

        Args:
            edits: List of find-replace edits to apply
            reasoning: Optional CONCISE reasoning for why these edits are being made

        Returns:
            Success message or error details
        """
        # Create document editor service
        editor_service = DocumentEditorService()

        # Pre-validate edits can be applied
        edit_result = editor_service.apply_edits(document.content, edits)
        if not edit_result.success:
            error_msg = f"Failed to apply edits to document: {'; '.join(edit_result.errors)}"
            # Return error immediately, no deferral needed
            return error_msg

        if not ctx.tool_call_approved:
            # This will show the edits to the user for approval
            raise ApprovalRequired()

        # Update document content and hash using repository
        document_repo.update_content(document, edit_result.content)

        return f"Edits applied successfully to {document.document_type}."

    return Tool(
        function=edit_document_tool,
        name=f"edit_{document.document_type}",
        requires_approval=True,
    )


def create_set_document_content_tool(document: Document, document_repo: DocumentRepository) -> Tool:
    """Create a tool for setting the initial content of a blank document.

    This tool is used when a document is empty and needs to be initialized with content.
    Once the document has content, use create_document_edit_tool instead.

    Args:
        document: Document model to set content for
        document_repo: Repository for document operations
    """

    def set_document_content_tool(ctx: RunContext[BaseDeps], content: str, reasoning: str = "") -> str:
        """Set the content of a blank document.

        Args:
            content: The full content to set for the document
            reasoning: Optional CONCISE reasoning for the content being set

        Returns:
            Success message or error details
        """
        # Validate the document is currently blank
        if document.content and document.content.strip():
            return f"Error: Document already has content. Use edit_{document.document_type} tool to make changes to existing content."

        # Validate content is not empty
        if not content or not content.strip():
            return "Error: Content cannot be empty."

        if not ctx.tool_call_approved:
            # This will show the content to the user for approval
            raise ApprovalRequired()

        # Update document content and hash using repository
        document_repo.update_content(document, content)

        return f"Content set successfully for {document.document_type}."

    return Tool(
        function=set_document_content_tool,
        name=f"set_{document.document_type}_content",
        requires_approval=True,
    )


async def get_relevant_context(ctx: RunContext[BaseDeps], resource_uri: str, query: str) -> str:
    """Get focused context from an ON_DEMAND resource.

    Use this tool when you need specific information from a resource that's
    only available as a description in the on_demand_resources list.

    Args:
        resource_uri: The URI of the resource to query (must be from on_demand_resources)
        query: Specific question about the resource

    Returns:
        Focused context relevant to your query
    """
    # Verify the resource is available
    available_uris = [res.uri for res in ctx.deps.on_demand_resources]
    if resource_uri not in available_uris:
        return f"Error: Resource {resource_uri} not available for this project"

    result = await ctx.deps.context_service.get_on_demand_context(resource_uri, query)
    return result


def create_text_search_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a text search tool using ripgrep for finding specific content within files.

    This tool searches through file contents using ripgrep, which is ideal for:
    - Finding function definitions, class declarations, or specific code patterns
    - Searching for error messages, log statements, or configuration values
    - Locating usage of specific variables, methods, or APIs
    - Finding TODO comments, FIXME markers, or code annotations

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def search_text_in_files(
        ctx: RunContext[BaseDeps],
        query: str,
        file_pattern: str | None = None,
        case_sensitive: bool = False,
        search_hidden: bool = False,
    ) -> str:
        """Search for text or regex patterns within file contents across the codebase.

        Use this tool when you need to:
        - Find specific function calls or method invocations
        - Locate error handling patterns or exception types
        - Search for configuration keys, environment variables, or constants
        - Find documentation or comment references to specific topics
        - Locate test cases or assertions related to specific functionality

        Examples:
        - search_text_in_files("def authenticate", file_pattern="*.py") - Find authentication functions
        - search_text_in_files("TODO.*security", case_sensitive=False) - Find security-related TODOs
        - search_text_in_files("import.*pandas", file_pattern="*.py") - Find pandas imports
        - search_text_in_files("error.*404", search_hidden=True) - Find 404 error references including hidden files

        Args:
            query: Text or regex pattern to search for. Supports full regex syntax.
            file_pattern: Optional glob pattern to filter files (e.g., '*.py', '*.ts', '**/*.json').
                         Use to focus search on specific file types or directories.
            case_sensitive: Whether search should be case sensitive. Default is False (case-insensitive).
            search_hidden: Whether to search hidden/ignored files like .git/, .venv/, node_modules/.
                          Default is False (skip hidden files).

        Returns:
            Formatted search results showing file:line:match for each occurrence,
            or a "No matches found" message if nothing was found.
        """
        result = await codebase_integration.search_file_content(
            query=query,
            file_pattern=file_pattern,
            case_sensitive=case_sensitive,
            search_hidden=search_hidden,
        )

        if not result:
            return f"No matches found for '{query}'"

        return "\n".join(result)

    return Tool(
        function=search_text_in_files,
        name="search_text_in_files",
    )


def create_file_search_tool(codebase_integration: CodebaseIntegration) -> Tool:
    """Create a file search tool using fd for finding files by name patterns.

    This tool searches for files by their names/paths using fd, which is ideal for:
    - Finding configuration files (e.g., config.json, .env files)
    - Locating test files or specific modules by name patterns
    - Discovering files with specific extensions across the codebase
    - Finding template files, documentation, or assets by name
    - Exploring project structure and file organization

    Args:
        codebase_integration: CodebaseIntegration instance for file system access
    """

    async def search_files_by_name(
        ctx: RunContext[BaseDeps],
        pattern: str,
        extension: str | None = None,
        exclude_pattern: str | None = None,
        search_hidden: bool = False,
    ) -> str:
        """Search for files by name patterns across the codebase using fd.

        Use this tool when you need to:
        - Find files with specific naming conventions or patterns
        - Locate configuration files, templates, or documentation
        - Discover test files or modules related to specific functionality
        - Explore project structure and understand file organization
        - Find files with specific extensions in certain directories

        Examples:
        - search_files_by_name("config", extension="json") - Find JSON config files
        - search_files_by_name("test.*auth", extension="py") - Find authentication test files
        - search_files_by_name(".*\\.env", search_hidden=True) - Find environment files including hidden ones
        - search_files_by_name("component", exclude_pattern="*.test.*") - Find component files excluding tests

        Args:
            pattern: Regex pattern to match file names/paths. Use regex syntax for complex patterns.
            extension: Optional file extension filter (e.g., 'py', 'ts', 'json').
                      Filters to only files with this extension.
            exclude_pattern: Optional pattern to exclude from results (e.g., '*.test.*', 'node_modules').
                           Useful for filtering out unwanted files.
            search_hidden: Whether to search hidden directories like .git/, .venv/.
                          Default is False (skip hidden directories).

        Returns:
            List of matching file paths relative to the codebase root,
            or a "No files found" message if no matches were found.
        """
        files = await codebase_integration.search_files(
            pattern=pattern,
            extension=extension,
            exclude_pattern=exclude_pattern,
            search_hidden=search_hidden,
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
        ctx: RunContext[BaseDeps],
        pattern: str,
        language: str | None = None,
    ) -> str:
        """Search for code structure patterns using AST-based matching.

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
        - search_code_structure("if __name__ == '__main__'") - Find main execution blocks

        Args:
            pattern: AST pattern using ast-grep syntax. Use $NAME for single nodes,
                    $$$ARGS for multiple nodes, and specific syntax for language constructs.
                    See ast-grep documentation for full pattern syntax.
            language: Optional language filter (e.g., 'python', 'typescript', 'rust', 'go').
                     Helps ast-grep parse files correctly and improves accuracy.

        Returns:
            Formatted search results showing file:line:column:match for each occurrence,
            or a "No matches found" message if no structural patterns were found.
        """
        result = await codebase_integration.search_code_structure(
            pattern=pattern,
            language=language,
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
        ctx: RunContext[BaseDeps],
        max_depth: int | None = None,
        subdirectory: str | None = None,
    ) -> str:
        """Display codebase git-tracked files in a hierarchical tree structure.

        Use this tool when you need to:
        - Get an overview of the project structure and organization
        - Understand how files and directories are organized
        - Find the general location of components or modules
        - Explore the codebase structure before diving into specific files
        - Document or communicate the project layout
        - Focus on a specific subdirectory's structure

        Examples:
        - show_directory_tree() - Show complete project structure
        - show_directory_tree(max_depth=2) - Show only top 2 levels for overview
        - show_directory_tree(subdirectory="src/my_project") - Show only files in src/my_project directory
        - show_directory_tree(max_depth=3, subdirectory="tests") - Show tests/ directory with 3 levels deep

        Args:
            max_depth: Maximum directory depth to display relative to subdirectory.
                      Use smaller values (1-3) for high-level overviews, or None for complete structure.
                      Helpful for large projects to avoid overwhelming output.
            subdirectory: Optional subdirectory to explore (e.g., 'src', 'tests', 'docs').
                         When specified, only shows files within that directory.
                         Do not include leading/trailing slashes.

        Returns:
            Formatted tree structure showing git-tracked files and directories,
            with proper indentation and tree characters for visualization.
        """
        tree = await codebase_integration.get_directory_tree(max_depth=max_depth, subdirectory=subdirectory)
        return tree

    return Tool(
        function=show_directory_tree,
    )
