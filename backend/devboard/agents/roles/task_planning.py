from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.base import AgentRole
from devboard.agents.roles.context_helpers import build_task_context
from devboard.agents.tools import (
    create_document_edit_tool,
    create_set_document_content_tool,
)
from devboard.agents.tools.implementation_plan_tools import (
    create_add_implementation_step_tool,
    create_edit_implementation_plan_overview_tool,
    create_edit_implementation_step_tool,
    create_remove_implementation_step_tool,
    create_set_implementation_plan_steps_tool,
)
from devboard.agents.tools.sub_agent_tools import create_task_codebase_investigation_tool
from devboard.agents.tools.task_tools import create_create_task_tool, create_edit_task_tool
from devboard.db.models import Task
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.task_implementation_plan import TaskImplementationPlanService
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
- Rich visual/structured content where it aids clarity (see VISUAL CONTENT section below)

**Exclude:**
- Implementation details or steps (reserved for Implementation Plan)
- Details not confirmed with the user
- Anything obvious or that adds length without reducing ambiguity

## VISUAL CONTENT

The frontend renders the following fenced code blocks as rich visual content — both in documents (task specification, implementation plan) and in conversation messages:
- **Tables** for comparing options, listing fields/properties, or summarising configurations
- **Mermaid diagrams** (` ```mermaid `) for component relationships, data flows, state machines, or sequence diagrams — rendered as interactive visual diagrams
- **HTML/SVG code blocks** (` ```html ` / ` ```svg `) for UI mockups, styled components, SVG diagrams, or interactive demos — rendered as live previews in a sandboxed iframe. Scripts are allowed to run (`allow-scripts`). Use these when visual fidelity matters more than what Mermaid or plain markdown can express.

Use these capabilities proactively:
- During **conversation**: include diagrams or HTML mockups in your messages when they help communicate ideas, illustrate proposals, or clarify requirements with the user
- In **task documents**: embed visual content in the task specification or implementation plan when it adds clarity for the reader (e.g. UI mockups for frontend tasks, flow diagrams for complex logic)

## IMPLEMENTATION PLAN

A structured plan consisting of discrete steps, each executable by a sub-agent. Use the `set_implementation_plan_steps` tool to create the plan.

**Before Drafting:**
Use `investigate_codebase` to research codebase patterns, conventions, and frameworks relevant to the implementation approach. This should cover things like: how similar features are structured, existing utilities or helpers that can be reused, naming conventions, testing patterns, and relevant framework usage. Use multiple parallel calls if investigating several areas.

**Step Structure:**
Each step should be self-contained with enough detail for a sub-agent to execute independently. Steps have:
- **title**: Short summary (e.g. "Add database models")
- **type**: One of:
  - `code_change` — implement the described changes **and write corresponding tests** for any new functionality introduced. Tests belong in the same step as the code they cover — do not split them out.
  - `documentation` — update or add documentation only
  - `validation` — run linting, type-checking, formatting, and the full test suite; fix any failures found. Not for writing new tests.
  - `code_review` — optional: review the git diff for correctness, quality, and alignment with the spec; produces findings for the coordination agent to act on (does not make changes directly). Include for non-trivial changes.
- **dependencies**: List of step numbers (1-indexed) that must complete first
- **details**: Detailed markdown instructions — include specific files, components, field names, and any non-obvious design decisions

**Designing Effective Steps:**
- Each step should represent a logical, independently deployable unit of work
- Break along natural seams: separate backend model changes from API layer changes, API from frontend, etc.
- Avoid steps that are too fine-grained (e.g. a single function) or too coarse (e.g. "implement everything")
- A step that another step depends on should be completable without knowledge of its dependents
- For `code_change` steps: specify which test files/patterns to follow so tests are written correctly alongside the code

**Recommended Step Ordering:**
1. Code change steps (with tests included) — ordered by logical dependency (e.g. data models before API before frontend)
2. One `validation` step depending on all code steps — runs the full quality gate and fixes any failures
3. (Optional) One `code_review` step depending on testing — for non-trivial changes; reviews the overall diff and fixes any issues

**Step Details Should Include:**
- Specific files/components to modify or create
- Relevant test file paths or patterns to follow
- Critical design details where non-obvious (field names/types, endpoint signatures, interfaces)
- Key design decisions or tradeoffs

**Step Details Should Exclude:**
- Content already in the Task Specification
- Full code snippets or verbatim implementation
- Design details obvious from existing patterns

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
5. **Create Implementation Plan**: Once user has approved the task specification, use the `set_implementation_plan_steps` tool to create a structured implementation plan with discrete steps for the user to review.

"""


class TaskPlanningAgentRole(AgentRole):
    """Role for task implementation planning."""

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
        task_service: TaskService,
        conversation_repo: ConversationRepository,
        conversation_id: int | None,
        plan_service: TaskImplementationPlanService | None = None,
    ):
        self.task = task
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service
        self.task_service = task_service
        self.conversation_repo = conversation_repo
        self.conversation_id = conversation_id
        self.plan_service = plan_service

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

        # Structured implementation plan tools
        if self.plan_service:
            tools.append(create_set_implementation_plan_steps_tool(self.task, self.plan_service))
            # Additional editing tools only if plan already exists
            if self.task.implementation_plan_structured:
                tools.extend(
                    [
                        create_add_implementation_step_tool(self.task, self.plan_service),
                        create_edit_implementation_step_tool(self.task, self.plan_service),
                        create_remove_implementation_step_tool(self.task, self.plan_service),
                        create_edit_implementation_plan_overview_tool(self.task, self.plan_service),
                    ]
                )
        else:
            # Fallback to Document-based implementation plan tools (backwards compat)
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
        tools.append(
            create_task_codebase_investigation_tool(
                self.task,
                self.agent_config_service,
                conversation_repo=self.conversation_repo,
                parent_conversation_id=self.conversation_id,
            )
        )

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
        return [
            "WebFetch",
            "WebSearch",
            "Read",
            "Skill",
            "Bash",
            "TaskCreate",
            "TaskGet",
            "TaskUpdate",
            "TaskList",
            "Task",
            "Agent",
        ]
