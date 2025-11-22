from pydantic_ai import Tool

from devboard.agents.roles.base import Role
from devboard.agents.tools import (
    create_code_structure_search_tool,
    create_directory_tree_tool,
    create_document_edit_tool,
    create_set_document_content_tool,
)
from devboard.db.models import Task
from devboard.db.repositories import DocumentRepository
from devboard.integrations.codebase import CodebaseIntegration

IMPLEMENTATION_SYSTEM_PROMPT = """
You are a Task Implementation Assistant for DevBoard, helping developers implement planned tasks.

Your role is to:
- Execute the implementation plan by making code changes to the codebase
- Follow best practices and coding standards
- Create clean, tested, production-ready code

AVAILABLE CAPABILITIES:
1. CODEBASE EDITING: Use Edit/Write tools to modify code files in the codebase
2. DOCUMENT EDITING: Use dedicated or virtual tools to update task specification and implementation plan
3. INVESTIGATION: Read files, search code, run bash commands for testing/verification

WORKFLOW:
- Review the implementation plan and understand requirements
- Create an internal to-do list of tasks to complete, based on implementation plan
- Make incremental changes following the plan's steps, updating the internal to-do list as progress is made
- Validate changes through testing where appropriate
- Ask for clarification when encountering ambiguity

IMPORTANT:
- Work incrementally - make atomic, logical changes
- Use the Edit tool for existing files, Write tool for new files
- Always provide clear reasoning for changes
- Task or Project documents are internally managed and NOT stored on the filesystem so cannot be viewed or edited like normal files
- After completing changes, respond with a VERY BRIEF and concise summary of changes made.
"""


def build_task_implementation_context(task: Task) -> str:
    """Build context for task implementation agent.

    Includes task metadata, codebase info, task specification, and implementation plan.
    Note: Project specification is intentionally excluded - implementation should follow
    the task specification and plan which already incorporate project context.

    Args:
        task: Task instance with eager-loaded relationships

    Returns:
        Formatted context string
    """
    return f"""
TASK NAME: {task.title}
TASK STATUS: {task.status.value}
RELEVANT CODEBASE:
- Name: {task.codebase.name}
- Worktree directory: {task.get_current_workspace_dir()}
- Description: {task.codebase.description or "N/A"}

TASK SPECIFICATION:
```markdown
{task.specification.content or "<EMPTY>"}
```

IMPLEMENTATION PLAN:
```markdown
{task.implementation_plan.content if task.implementation_plan else "<EMPTY>"}
```
"""


class TaskImplementationRole(Role):
    """Role for task implementation in a codebase."""

    def __init__(self, task: Task, document_repository: DocumentRepository):
        """Initialize task implementation role.

        Args:
            task: Task instance
            document_repository: Repository for document operations
        """
        self.task = task
        self.document_repository = document_repository

    def get_system_prompt(self) -> str:
        """Get the system prompt for task implementation role."""
        return IMPLEMENTATION_SYSTEM_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for task implementation role.

        Returns:
            List of document editing tools for specification and implementation plan.
            Note: Codebase editing tools (Edit/Write) are provided directly by the
            underlying agent (ClaudeCode), not through this role.
        """
        if not self.task.implementation_plan:
            raise ValueError(f"Task (ID: {self.task.id}) must have an implementation plan for implementation agent")

        codebase_integration = CodebaseIntegration(self.task.get_current_workspace_dir())

        tools = [
            # Tools for task specification document (uses default approval behavior)
            create_set_document_content_tool(self.task.specification, self.document_repository),
            create_document_edit_tool(self.task.specification, self.document_repository),
            # Tools for implementation plan document (never require approval)
            create_set_document_content_tool(
                self.task.implementation_plan, self.document_repository, requires_approval=False
            ),
            create_document_edit_tool(self.task.implementation_plan, self.document_repository, requires_approval=False),
            create_code_structure_search_tool(codebase_integration),
            create_directory_tree_tool(codebase_integration),
        ]

        return tools

    async def get_context_content(self) -> str:
        """Get context content for task implementation role.

        Returns:
            Formatted context containing task details, specification, and implementation plan
        """
        return build_task_implementation_context(self.task)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role."""
        return ["Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch", "Task", "Write"]
