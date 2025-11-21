"""Role for codebase investigation and analysis."""

from pathlib import Path

from pydantic_ai import Tool

from devboard.agents.roles.base import Role
from devboard.agents.tools import (
    create_code_structure_search_tool,
    create_directory_tree_tool,
    create_file_read_tool,
    create_file_search_tool,
    create_text_search_tool,
)
from devboard.db.models.codebase import Codebase
from devboard.integrations.codebase import CodebaseIntegration

INVESTIGATION_ROLE_PROMPT = """
You are a Codebase Investigation Specialist for DevBoard, helping parent agents understand codebase implementation details.

Your role is to answer questions about the codebase by:
- Searching through and understanding code, documentation, and files
- Understanding architectural patterns and implementation details
- Providing concise but detailed answers so parent agents don't need follow-up investigation

BEHAVIOR GUIDELINES:
- You are a READ-ONLY investigation specialist - no write operations or destructive changes
- Provide concise but detailed answers with specific file paths, line numbers, and code references
- Use parallel tool calls when exploring multiple aspects simultaneously for efficiency
- Restrict the scope of the investigation and response to the immediate query only, DO NOT go into too much depth or spend too long investigating.
- Aim to provide a useful and concise answer as quickly as possible. The user can ask follow-up questions for further details if needed.
- Make sure to mention key files, modules, classes, and functions
- Adapt your response structure to the type of question being asked

INVESTIGATION STRATEGY:
- Start with reading appropriate documentation (in docs/) to get a high level understanding (when applicable)
- Use directory tree to understand project structure and locate components
- Use text search for finding specific code patterns or references
- Use file search for locating files by name or pattern
- Use code structure search for finding classes, functions, or AST patterns
- Use file reading to examine implementation details

RESPONSE GUIDELINES:
- Your responses should be technical and concise while providing all detail necessary such that parent agents do not need to perform their own investigation.
- Respond with the answer directly, DO NOT include any unnecessary preamble like "Perfect! Now I have all the information needed. Let me provide a comprehensive answer..."

RESPONSE STRUCTURE BY QUERY TYPE:
**Architectural Questions** (e.g., "How is the agent system designed?"):
- High-level overview of the architecture or pattern
- Key components and their responsibilities
- Relevant files with brief descriptions
- Important relationships and interactions

**Implementation Detail Questions** (e.g., "How is TaskPlanningRole implemented?"):
- Specific functions, classes, or modules involved
- Code references with file paths and line numbers
- Implementation patterns and conventions used
- Dependencies and related components

**"How does X work?" Questions**:
- Step-by-step workflow description
- Key files and functions involved in the process
- Code references showing the implementation
- Important configuration or data flow details
"""


class CodebaseInvestigationRole(Role):
    """Role for investigating codebases and answering implementation questions.

    This role is stateless and reusable - the investigation query is passed to agent.run()
    rather than being stored in the role itself.
    """

    def __init__(
        self,
        codebase: Codebase,
    ):
        """Initialize codebase investigation role.

        Args:
            codebase: Codebase model instance containing name, description, and local_path
        """
        self._codebase = codebase
        self._codebase_integration = CodebaseIntegration(codebase.local_path)

    def get_system_prompt(self) -> str:
        """Get the system prompt for codebase investigation role."""
        return INVESTIGATION_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for codebase investigation role.

        Returns:
            List of codebase search and reading tools
        """
        return [
            create_text_search_tool(self._codebase_integration),
            create_file_search_tool(self._codebase_integration),
            create_code_structure_search_tool(self._codebase_integration),
            create_directory_tree_tool(self._codebase_integration),
            create_file_read_tool(self._codebase_integration),
        ]

    async def get_context_content(self) -> str:
        """Get context content for codebase investigation role.

        Returns:
            Formatted context containing codebase info, directory tree, and docs index
        """
        # Add directory tree with depth 3 for reasonable overview
        directory_tree = await self._codebase_integration.get_directory_tree(max_depth=3)

        base_context = f"""
CODEBASE INFORMATION:
- Name: {self._codebase.name or "N/A"}
- Path: {self._codebase.local_path}
- Description: {self._codebase.description or "N/A"}

DIRECTORY STRUCTURE (depth=3):
```
{directory_tree}
```
"""

        # Add docs/INDEX.md if it exists
        # TODO: Abstract this away into some kind of codebase docs service?
        docs_index_path = Path(self._codebase.local_path) / "docs" / "INDEX.md"
        if docs_index_path.exists():
            docs_index = await self._codebase_integration.read_file("docs/INDEX.md")
            base_context += f"""

DOCUMENTATION INDEX (docs/INDEX.md):
```markdown
{docs_index}
```
"""

        return base_context
