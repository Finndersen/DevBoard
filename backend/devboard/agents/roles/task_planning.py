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
- Reference existing content from the Task Specification document where applicable, instead of repeating it.

Keep it as concise as possible while capturing all necessary detail to be actionable (NOT ALREADY INCLUDED IN THE TASK SPECIFICATION), including:
- **Analysis Summary**: High-level overview of the technical analysis and architecture understanding
- **Current Implementation Details**: Context about relevant files, functions, classes, types, data structures etc (if not already captured in the task specification document)
- **Implementation Steps**: Concise steps with specific files, functions, or components to modify/create. Capture the intent and critical functional changes for review, but do NOT include granular details of code changes. Indicate which steps can be executed in parallel where relevant
- **Code Changes**: HIGH LEVEL description of what changes are needed (e.g., "Update function X in file Y to...")
- **Data/Schema Changes**: Database migrations, model updates, or data structure changes if applicable
- **Testing Strategy**: High level overview of tests to be added or updated

It should NOT include:
- ❌ NO Duplication of information already captured in the task specification document (can reference it if required)
- ❌ NO Full code change snippets or specific implementation details (implementation agent can decide)
- ❌ NO Implementation time estimates

BEHAVIOUR GUIDELINES:
- You are in DESIGN AND PLANNING mode and not able to make any destructive changes other than editing the Task Specification and Implementation Plan Document.
- Task and Project documents are internally managed and NOT stored on the filesystem so CANNOT be viewed or edited like normal files
- Thoroughly analyze the task specification, codebase and any other relevant associated resources before proposing a plan
- Research the existing codebase to understand current implementation patterns, conventions, and architecture
- Ask clarifying questions about technical decisions, edge cases, or ambiguous requirements
- Discuss tradeoffs between different implementation approaches
- Be critical and point out potential issues, risks, or better alternatives
- Break down complex tasks into logical, manageable steps
- Make sure to consider and investigate impacts and required changes to tests and other related components (e.g. frontend, backend, database)
- ONLY make changes to the implementation plan when explicitly instructed by the user, or after asking and receiving confirmation
- ONLY include content in the implementation plan that is not already in the Task Specification Document. If the Task Specification is quite comprehensive, then the implementation plan should be a concise list of changes to be made
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

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService | None = None,
    ):
        """Initialize task planning role.

        Args:
            task: Task instance
            document_repository: Repository for document operations
            agent_config_service: Optional service for agent configuration (required for investigation tool)
        """
        self.task = task
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service

    def get_system_prompt(self) -> str:
        """Get the system prompt for task planning role."""
        return PLANNING_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for task planning role.

        Returns:
            List of document editing tools for both specification and implementation plan,
            plus codebase search tools and investigation tool (if codebase available)
        """
        tools: list[Tool] = [
            # Tools for task specification document
            create_document_edit_tool(self.task.specification, self.document_repository),
        ]

        # Tools for implementation plan document (never require approval)
        if self.task.implementation_plan:
            tools.append(
                create_set_document_content_tool(
                    self.task.implementation_plan, self.document_repository, requires_approval=False
                )
            )
            if self.task.implementation_plan.content:
                tools.append(
                    create_document_edit_tool(
                        self.task.implementation_plan, self.document_repository, requires_approval=False
                    )
                )

        # Add codebase investigation tool if codebase is configured
        if self.task.codebase:
            tools.append(
                create_codebase_investigation_tool(
                    [self.task.codebase],
                    self.agent_config_service,
                )
            )

        return tools

    async def get_context_content(self) -> str:
        """Get context content for task planning role.

        Returns:
            Formatted context containing task details, project spec, task spec, and implementation plan
        """
        return build_task_planning_context(self.task)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role."""
        return ["WebFetch", "WebSearch", "Task"]
