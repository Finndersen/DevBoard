from pydantic_ai import Tool

from devboard.agents.roles.base import Role
from devboard.agents.tools import (
    create_code_structure_search_tool,
    create_directory_tree_tool,
    create_document_edit_tool,
    create_file_search_tool,
    create_set_document_content_tool,
    create_text_search_tool,
)
from devboard.db.models import Task
from devboard.db.repositories import DocumentRepository
from devboard.integrations.codebase import CodebaseIntegration

SPECIFICATION_ROLE_PROMPT = """
You are a Task Specification Assistant for DevBoard, helping developers craft detailed task specifications.

Your role is to help create or iteratively improve the Task Specification document (task description) based on:
- User input and requirements
- Context from the project (GitHub, Jira, Slack, Codebase)
- Best practices for clear technical specifications

A task should correspond to an atomic piece of work, such as a specific feature, bug fix, or improvement.

TASK SPECIFICATION DOCUMENT GUIDELINES:
The task specification should be clear, actionable and as concise as possible while still containing enough important information to develop an implementation plan
It should include:
- ✅ A clear, specific goal statement
- ✅ Functional requirements and constraints
- ✅ Any relevant background information or context of current state

It should NOT include:
- ❌ Implementation details or steps (A dedicated Implementation Plan document will be created for that)
- ❌ Unnecessary duplication of information, or superfluous details that are not critical for implementation
- ❌ Details that have NOT been discussed and confirmed with the user

BEHAVIOUR GUIDELINES:
- Discuss with the user to understand the task requirements and goals, and ask clarifying questions as needed in order to arrive at a mutual understanding, which you should articulate.
- Ask clarification questions to the user directly BEFORE creating or editing the task specification, do NOT include them in the task specification itself.
- ONLY make changes to the task specification when explicitly instructed by the user, or after asking and receiving confirmation (once you have a mutual understanding of the task requirements and goals).
- Identify and explore gaps or ambiguity in the task specification, raise potential issues or edge cases
- Challenge the user and be critical of ideas where appropriate, suggest improvements or alternative approaches
- DO NOT make any file edits or other destructive changes other than editing the Task Specification Document
- Your responses should be concise, helpful, accurate, and focused on creating a clear, actionable specification.
- Task or Project documents are internally managed and NOT stored on the filesystem so cannot be viewed or edited like normal files
"""


def build_task_specification_context(task: Task) -> str:
    """Build context for task specification agent.

    Includes task metadata, project specification, and task specification document.

    Note: Requires task to be loaded within an active SQLAlchemy session,
    as it will lazy-load the project relationship if needed.

    Args:
        task: Task instance with eager-loaded documents

    Returns:
        Formatted context string
    """
    context = f"""
TASK NAME: {task.title}
TASK STATUS: {task.status.value}

PROJECT SPECIFICATION:
```markdown
{task.project.specification.content or "<EMPTY>"}
```

TASK SPECIFICATION DOCUMENT (Dynamically updated live state):
```markdown
{task.specification.content or "<EMPTY>"}
```
"""
    if task.codebase:
        context += f"""
    RELEVANT CODEBASE:
    - Name: {task.codebase.name}
    - Local Path: {task.codebase.local_path}
    - Description: {task.codebase.description or "N/A"}
    """

    return context


class TaskSpecificationRole(Role):
    """Role for task specification creation and management."""

    def __init__(self, task: Task, document_repository: DocumentRepository):
        """Initialize task specification role.

        Args:
            task: Task instance
            document_repository: Repository for document operations
        """
        self.task = task
        self.document_repository = document_repository
        self.codebase_integration = CodebaseIntegration(task.codebase.local_path) if task.codebase else None

    def get_system_prompt(self) -> str:
        """Get the system prompt for task specification role."""
        return SPECIFICATION_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for task specification role.

        Returns:
            List of document editing tools and codebase search tools (if codebase available)
        """
        tools: list[Tool] = [
            create_set_document_content_tool(self.task.specification, self.document_repository),
            create_document_edit_tool(self.task.specification, self.document_repository),
        ]

        # Add codebase search tools if codebase is configured
        if self.codebase_integration:
            tools.extend(
                [
                    create_text_search_tool(self.codebase_integration),
                    create_file_search_tool(self.codebase_integration),
                    create_code_structure_search_tool(self.codebase_integration),
                    create_directory_tree_tool(self.codebase_integration),
                ]
            )

        return tools

    async def get_context_content(self) -> str:
        """Get context content for task specification role.

        Returns:
            Formatted context containing task details, project spec, and task spec
        """
        return build_task_specification_context(self.task)
