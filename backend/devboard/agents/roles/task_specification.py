from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.base import Role
from devboard.agents.tools import (
    create_codebase_investigation_tool,
    create_document_edit_tool,
    create_set_document_content_tool,
)
from devboard.db.models import Task
from devboard.db.repositories import DocumentRepository

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

The length and level of detail of the task specification should be proportional to the complexity and scope of the task. For simple tasks, a concise goal statement and functional requirements may be sufficient.

BEHAVIOUR GUIDELINES:
- You are in DESIGN AND PLANNING mode and not able to make any destructive changes other than editing the Task Specification Document.
- Discuss with the user to understand the task requirements and goals, and ask clarifying questions as needed in order to arrive at a mutual understanding, which you should articulate.
- Ask clarification questions to the user directly BEFORE creating or editing the task specification, do NOT include them in the task specification itself.
- ONLY make changes to the task specification when explicitly instructed by the user, or after asking and receiving confirmation (once you have a mutual understanding of the task requirements and goals).
- Identify and explore gaps or ambiguity in the task specification, raise potential issues or edge cases
- Challenge the user and be critical of ideas where appropriate, suggest improvements or alternative approaches
- Make sure to consider and investigate impacts and required changes to tests and other related components (e.g. frontend, backend, database)
- DO NOT make any file edits or other destructive changes other than editing the Task Specification Document
- Use the investigate_codebase tool to answer questions about functionality, implementation details, architecture, and code organization (use multiple parallel calls if needed).
- Your responses should be concise, helpful, accurate, and focused on creating a clear, actionable specification.
- Task or Project documents are "virtual documents" - they internally managed and NOT stored on the filesystem so cannot be viewed or edited like normal files
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

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
    ):
        """Initialize task specification role.

        Args:
            task: Task instance
            document_repository: Repository for document operations
            agent_config_service: Optional service for agent configuration (required for investigation tool)
        """
        self.task = task
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service

    def get_system_prompt(self) -> str:
        """Get the system prompt for task specification role."""
        return SPECIFICATION_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for task specification role.

        Returns:
            List of document editing tools, codebase search tools, and investigation tool (if codebase available)
        """
        tools: list[Tool] = [
            create_set_document_content_tool(self.task.specification, self.document_repository),
        ]

        if self.task.specification.content:
            tools.append(create_document_edit_tool(self.task.specification, self.document_repository))

        if self.task.codebase:
            # Add investigation tool
            tools.append(
                create_codebase_investigation_tool(
                    self.task.codebase,
                    self.agent_config_service,
                )
            )

        return tools

    async def get_context_content(self) -> str:
        """Get context content for task specification role.

        Returns:
            Formatted context containing task details, project spec, and task spec
        """
        return build_task_specification_context(self.task)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role."""
        return ["WebFetch", "WebSearch", "Task"]
