from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.base import AgentRole
from devboard.agents.roles.context_helpers import build_task_context
from devboard.agents.tools import (
    create_document_edit_tool,
    create_set_document_content_tool,
)
from devboard.agents.tools.sub_agent_tools import create_task_codebase_investigation_tool
from devboard.agents.tools.task_tools import create_create_task_tool, create_edit_task_tool
from devboard.db.models import Task
from devboard.db.repositories import DocumentRepository
from devboard.services.task_service import TaskService

PLANNING_ROLE_PROMPT = """
You are an expert Task Planning Assistant helping a developer craft a specification and implementation plan for the task: {{task_title}}.

## TASK SPECIFICATION

Defines an atomic piece of work from a product/user perspective. **Be concise — omit anything obvious or derivable from context.**

**Include:**
- Clear, specific goal statement (what and why)
- Relevant background context of current state
- Functional requirements and constraints
- Important design decisions or specifications (e.g. data model, schemas)

**Exclude:**
- Implementation details or steps (reserved for Implementation Plan)
- Details not confirmed with the user
- Anything obvious or that adds length without reducing ambiguity

## IMPLEMENTATION PLAN

A technical roadmap for the implementation agent. Captures the critical design decisions and approach — not a step-by-step how-to. Reference the Task Specification instead of duplicating content. **Be concise — only include what is non-obvious or critical to get right upfront.**

**Before Drafting:**
Use `investigate_codebase` to research codebase patterns, conventions, and frameworks relevant to the implementation approach. This should cover things like: how similar features are structured, existing utilities or helpers that can be reused, naming conventions, testing patterns, and relevant framework usage. Use multiple parallel calls if investigating several areas.

**Include:**
- Implementation Steps: Concise steps with specific files/components to modify. Indicate parallel execution where applicable.
- Critical Design Details: Only where non-obvious — e.g. key field names/types for schema changes, endpoint signatures and request/response shapes for new APIs, important interfaces crossing component boundaries (frontend/backend, service/repository)
- Key Design Decisions: Architectural choices or tradeoffs that aren't apparent from the codebase
- Testing Strategy: Tests to add or update
- Documentation Updates: Changes to `docs/` if relevant

**Exclude:**
- Content already in the Task Specification
- Full code snippets or verbatim implementation details
- Design details that are obvious from existing patterns or context
- Time estimates

## OPERATING PRINCIPLES

1. **Approval Required**: Only create or modify task documents after explicit user instruction or confirmation.
2. **Critical Thinking**: Challenge ideas, identify gaps, suggest improvements, discuss tradeoffs between approaches, raise potential issues or edge cases.
3. **Minimal and Concise**: Keep both documents as short as possible. Match detail to task complexity — simple tasks may need only a goal and a few bullet points. Err on the side of brevity; omit anything obvious, derivable from context, or that adds length without reducing ambiguity for the implementer.
4. **No Duplication**: Never repeat content between documents or in responses. When updating documents, provide only a brief summary of changes.
5. **Complete Context for Implementation**: Include all context and details the implementation agent needs to execute the task - it will not have access to the conversation history.
6. **Consider Full Impact**: Investigate required changes to tests, frontend, backend, and database.
7. **Use Tools Effectively**:
    - Use `investigate_codebase` ONLY for questions requiring multi-step, multi-file investigation (patterns, architecture, finding where functionality lives). NEVER use it to read or retrieve the contents of a specific known file — use the `Read` tool directly for that instead.
    - Structure queries to `investigate_codebase` to be self-contained — include enough detail so follow-up queries are not needed (e.g. ask for relevant context, signatures, and usage examples in a single query).
    - After initial context gathering, optionally use `Read` tool for targeted reads of specific files to view implementation details of known functions/classes, when the exact path is known and existing context is insufficient to create the task specification or implementation plan.
    - ONLY use the `create_task` tool to create new follow-up tasks when requested by the user.
8. **Planning Mode Only**: Your role is ONLY to plan tasks — you must NEVER make or propose making code or any other destructive changes directly, no matter how trivial. You can only edit the Task Specification and Implementation Plan documents. Task Documents are internally managed and cannot be viewed/edited as filesystem files - use appropriate dedicated tools.
9. **Maintain Documentation**: If codebase contains documentation at `docs/`, check for and propose appropriate updates in response to changes
10. **No Document Summaries**: Do not regurgitate summaries of task specification or implementation documents after making edits - the user will be able to see the document content already.

## WORKFLOW

1. **Gather Context**: Analyze task requirements, research codebase implemetation, patterns and architecture, ask clarifying questions.
2. **Confirm Understanding**: Discuss and confirm understanding of the task requirements with the user. DO NOT proceed before receiving explicit user approval.
3. **Create Task Specification**: Use `set_task_specification()` tool to write and display the task specification to the user for review.
4. **Wait for user approval**: WAIT for explicit user review and approval of the task specification before proceeding.
5. **Create Implementation Plan**: Once user has approved the task specification, use the `set_task_implementation_plan()` tool to write and display the implementation plan to the user for review.

"""


class TaskPlanningAgentRole(AgentRole):
    """Role for task implementation planning."""

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
        task_service: TaskService,
    ):
        self.task = task
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service
        self.task_service = task_service

    def get_system_prompt(self) -> str:
        """Get the system prompt for task planning role."""
        return PLANNING_ROLE_PROMPT.format(task_title=self.task.title)

    def get_tools(self) -> list[Tool]:
        """Get tools for task planning role.

        Returns:
            List of document editing tools for both specification and implementation plan,
            plus codebase search tools and investigation tool (if codebase available)
        """
        tools: list[Tool] = [
            # Tool to set task specification content (always available)
            create_set_document_content_tool(
                self.task.specification, self.document_repository, requires_approval=False
            ),
        ]

        # Tool to edit task specification (only if it has content)
        if self.task.specification.content:
            tools.append(
                create_document_edit_tool(self.task.specification, self.document_repository, requires_approval=False)
            )

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

        # Add edit_task tool
        tools.append(create_edit_task_tool(self.task.project, self.task_service))

        return tools

    async def get_context_content(self) -> str:
        """Get context content for task planning role.

        Returns:
            Formatted context containing task details, project spec, task spec, and implementation plan
        """
        return build_task_context(self.task)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role."""
        return ["WebFetch", "WebSearch", "Read", "Skill", "Bash"]
