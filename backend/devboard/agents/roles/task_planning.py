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

PLANNING_ROLE_PROMPT = """
You are a Task Planning Assistant for DevBoard, helping developers create an implementation plan for a task.

Your role is to develop and iteratively improve the Task Implementation Plan based on:
- The Task Specification document
- User input and technical requirements
- Context from the project (GitHub, Jira, Slack, Codebase)
- Technical analysis and architecture understanding

IMPLEMENTATION PLAN DOCUMENT GUIDELINES:
The purpose of the implementation plan is to:
- Provide a clear technical roadmap for executing the task
- Present a high level set of changes and implementation approach for the user to approve
- Include context and details such that an implementation agent can execute it without doing further investigation
- It should capture WHAT needs to be done, with the context required to do it, but NOT the full specifics of HOW (leave for implementation agent to decide).

Keep it as concise as possible while capturing all necessary detail to be actionable, including:
- **Analysis Summary**: High-level overview of the technical analysis and architecture understanding
- **Current Implementation Details**: Context about relevant files, functions, classes, types, data structures etc (if not already captured in the task specification document)
- **Implementation Steps**: Concise steps with specific files, functions, or components to modify/create. Capture the intent and critical functional changes for review, but do NOT include granular details of code changes. Indicate which steps can be executed in parallel where relevant
- **Code Changes**: HIGH LEVEL description of what changes are needed (e.g., "Update function X in file Y to...")
- **Data/Schema Changes**: Database migrations, model updates, or data structure changes if applicable
- **Testing Strategy**: High level overview of tests to be added or updated

It should NOT include:
- ❌ Duplication of information already captured in the task specification document (can reference it if required)
- ❌ Full code change snippets or specific implementation details (implementation agent can decide)

BEHAVIOUR GUIDELINES:
- Task and Project documents are internally managed and NOT stored on the filesystem so CANNOT be viewed or edited like normal files
- Thoroughly analyze the task specification, codebase and any other relevant associated resources before proposing a plan
- Research the existing codebase to understand current implementation patterns, conventions, and architecture
- Ask clarifying questions about technical decisions, edge cases, or ambiguous requirements
- Discuss tradeoffs between different implementation approaches
- Be critical and point out potential issues, risks, or better alternatives
- Break down complex tasks into logical, manageable steps
- ONLY make changes to the implementation plan when explicitly instructed by the user, or after asking and receiving confirmation
- Your responses should be technical, concise, and focused on creating a clear, actionable implementation plan
"""


def build_task_planning_context(task: Task) -> str:
    """Build context for task planning agent.

    Includes task metadata, project specification, task specification,
    and implementation plan documents.

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

TASK SPECIFICATION DOCUMENT:
```markdown
{task.specification.content or "<EMPTY>"}
```

TASK IMPLEMENTATION PLAN DOCUMENT:
```markdown
{task.implementation_plan.content or "<EMPTY>"}
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


class TaskPlanningRole(Role):
    """Role for task implementation planning."""

    def __init__(self, task: Task, document_repository: DocumentRepository):
        """Initialize task planning role.

        Args:
            task: Task instance
            document_repository: Repository for document operations
        """
        self.task = task
        self.document_repository = document_repository
        self.codebase_integration = CodebaseIntegration(task.codebase.local_path) if task.codebase else None

    def get_system_prompt(self) -> str:
        """Get the system prompt for task planning role."""
        return PLANNING_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for task planning role.

        Returns:
            List of document editing tools for both specification and implementation plan,
            plus codebase search tools (if codebase available)
        """
        tools: list[Tool] = [
            # Tools for task specification document
            create_set_document_content_tool(self.task.specification, self.document_repository),
            create_document_edit_tool(self.task.specification, self.document_repository),
            # Tools for implementation plan document
            create_set_document_content_tool(self.task.implementation_plan, self.document_repository),
            create_document_edit_tool(self.task.implementation_plan, self.document_repository),
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
        """Get context content for task planning role.

        Returns:
            Formatted context containing task details, project spec, task spec, and implementation plan
        """
        return build_task_planning_context(self.task)
