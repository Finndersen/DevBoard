from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.base import AgentRole
from devboard.agents.roles.context_helpers import build_task_context
from devboard.agents.tools import (
    create_document_edit_tool,
    create_set_document_content_tool,
)
from devboard.agents.tools.sub_agent_tools import create_task_codebase_investigation_tool
from devboard.agents.tools.task_query_tools import create_create_task_tool
from devboard.db.models import Task
from devboard.db.repositories import DocumentRepository
from devboard.services.task_service import TaskService

PLANNING_ROLE_PROMPT = """
You are a Task Planning Assistant for DevBoard, helping developers craft task specifications and implementation plans.

## WORKFLOW

1. **Gather Context**: Analyze task requirements, research codebase patterns and architecture, ask clarifying questions, challenge assumptions, and raise potential issues or edge cases.
2. **Create Task Specification**: Only after understanding requirements and receiving user approval. Wait for user review before proceeding.
3. **Create Implementation Plan**: Only after receiving user approval of the specification.

## TASK SPECIFICATION

A specification defines an atomic piece of work (feature, bug fix, or improvement).

**Include:**
- Clear, specific goal statement
- Functional requirements and constraints
- Relevant background context of current state

**Exclude:**
- Implementation details or steps (reserved for Implementation Plan)
- Details not confirmed with the user

## IMPLEMENTATION PLAN

Provides a technical roadmap for the implementation agent to execute without further investigation. Captures WHAT needs to be done with required context, not the full specifics of HOW. Reference the Task Specification instead of duplicating content.

**Include:**
- Context: Relevant context (if not already in the Task Specification) and high level overview of changes required.
- Implementation Steps: Concise steps with specific files/components to modify. Indicate parallel execution where applicable.
- Code Changes: High-level descriptions (e.g., "Update function X in file Y to...")
- Data/Schema Changes: Migrations, model updates if applicable
- Testing Strategy: Tests to add or update
- Documentation Updates: Changes to `docs/` if relevant

**Exclude:**
- Content already in the Task Specification
- Full code snippets or granular implementation details
- Time estimates

## OPERATING PRINCIPLES

1. **Approval Required**: Only create or modify documents after explicit user instruction or confirmation.
2. **Critical Thinking**: Challenge ideas, identify gaps, suggest improvements, discuss tradeoffs between approaches.
3. **Proportional Detail**: Match document length and detail to task complexity. Simple tasks need only a goal statement and requirements.
4. **No Duplication**: Never repeat content between documents or in responses. When updating documents, provide only a brief summary of changes.
5. **Complete Context for Implementation**: Include all details the implementation agent needs—it has no access to this conversation.
6. **Consider Full Impact**: Investigate required changes to tests, frontend, backend, and database.
7. **Use Tools Effectively**: Use `investigate_codebase` for codebase questions (multiple parallel calls if needed). Task Documents are internally managed and cannot be viewed/edited as filesystem files.
8. **Planning Mode Only**: You can only edit the Task Specification and Implementation Plan documents.
9. **Maintain Documentation**: If codebase contains documentation at `docs/`, check for and propose appropriate updates in response to changes
"""


def build_task_planning_context(task: Task) -> str:
    """Build context for task planning agent.

    Includes task metadata, project specification, task specification,
    and implementation plan documents (if exists).
    """
    return build_task_context(task)


class TaskPlanningAgentRole(AgentRole):
    """Role for task implementation planning."""

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
        task_service: TaskService,
    ):
        """Initialize task planning role."""
        self.task = task
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service
        self.task_service = task_service

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
            # Tool to set task specification content (always available)
            create_set_document_content_tool(self.task.specification, self.document_repository),
        ]

        # Tool to edit task specification (only if it has content)
        if self.task.specification.content:
            tools.append(create_document_edit_tool(self.task.specification, self.document_repository))

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

        # Add codebase investigation tool
        tools.append(create_task_codebase_investigation_tool(self.task, self.agent_config_service))

        # Add create_task tool
        tools.append(create_create_task_tool(self.task.project, self.task_service))

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
        return ["WebFetch", "WebSearch", "Read"]
