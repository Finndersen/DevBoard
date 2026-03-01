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
from devboard.db.models import CustomFieldDefinition, Task
from devboard.db.repositories import DocumentRepository
from devboard.services.task_service import TaskService

PLANNING_ROLE_PROMPT = """
You are a Task Planning Assistant for DevBoard, helping developers craft task specifications and implementation plans.

## WORKFLOW

1. **Gather Context**: Analyze task requirements, research codebase implemetation, patterns and architecture, ask clarifying questions.
2. **Create Task Specification**: ONLY after understanding requirements and receiving user approval, use `set_task_specification()` tool to write and display the task specification to the user for review. Then WAIT for explicit user review and approval before proceeding.
3. **Create Implementation Plan**: ONLY after receiving user approval of the specification. Use `set_task_implementation_plan()` tool to write and display the task specification to the user

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

**Before Drafting:**
Use `investigate_codebase` to research codebase patterns, conventions, and frameworks relevant to the implementation approach. This should cover things like: how similar features are structured, existing utilities or helpers that can be reused, naming conventions, testing patterns, and relevant framework usage. Use multiple parallel calls if investigating several areas.

**Include:**
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
2. **Critical Thinking**: Challenge ideas, identify gaps, suggest improvements, discuss tradeoffs between approaches, raise potential issues or edge cases.
3. **Proportional Detail**: Match document length and detail to task complexity. Simple tasks need only a goal statement and requirements.
4. **No Duplication**: Never repeat content between documents or in responses. When updating documents, provide only a brief summary of changes.
5. **Complete Context for Implementation**: Include all context and details the implementation agent needs to execute the task - it will not have access to the conversation history.
6. **Consider Full Impact**: Investigate required changes to tests, frontend, backend, and database.
7. **Use Tools Effectively**:
    - Use `investigate_codebase` for any codebase question that may involve searching or reading multiple files.
    - Structure queries to `investigate_codebase` to be self-contained — include enough detail so follow-up queries are not needed (e.g. ask for relevant context, signatures, and usage examples in a single query).
    - After initial context gathering, optionally use `Read` tool for targeted reads of specific files to view implemetnation details of known functions/classes, when the exact path is known and existing context is insufficient to create the task specification or implementation plan.
8. **Planning Mode Only**: You can only edit the Task Specification and Implementation Plan documents. Task Documents are internally managed and cannot be viewed/edited as filesystem files - use appropriate dedicated tools.
9. **Maintain Documentation**: If codebase contains documentation at `docs/`, check for and propose appropriate updates in response to changes
10. **No Document Summaries**: Do not regurgitate summaries of task specification or implementation documents after making edits - the user will be able to see the document content already.
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
        custom_field_definitions: list[CustomFieldDefinition] | None = None,
    ):
        self.task = task
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service
        self.task_service = task_service
        self.custom_field_definitions = custom_field_definitions

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
        tools.append(create_create_task_tool(self.task.project, self.task_service, self.custom_field_definitions))

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
