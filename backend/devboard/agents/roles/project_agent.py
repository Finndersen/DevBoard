"""Project agent role for managing specifications, tasks, and lifecycle."""

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.roles.base import AgentRole
from devboard.agents.tools import (
    create_branch_conversation_tool,
    create_document_edit_tool,
    create_inspect_conversation_tool,
    create_refocus_conversation_tool,
    create_set_document_content_tool,
)
from devboard.agents.tools.codebase_management_tools import (
    create_update_codebase_tool,
    create_view_codebase_details_tool,
)
from devboard.agents.tools.project_tools import (
    create_complete_initiative_tool,
    create_complete_project_tool,
    create_create_initiative_tool,
    create_edit_initiative_context_tool,
    create_list_project_initiatives_tool,
    create_set_initiative_context_content_tool,
    create_view_initiative_details_tool,
)
from devboard.agents.tools.sub_agent_tools import CodebaseInvestigationContext, create_multi_codebase_investigation_tool
from devboard.agents.tools.task_agent_tools import (
    create_get_task_agent_status_tool,
    create_send_task_agent_prompt_tool,
)
from devboard.agents.tools.task_tools import (
    create_create_task_tool,
    create_edit_task_tool,
    create_list_tasks_tool,
    create_view_task_details_tool,
)
from devboard.db.models import Project, Task
from devboard.db.repositories import (
    CodebaseRepository,
    ConversationRepository,
    DocumentRepository,
    InitiativeRepository,
    LogEntryRepository,
)
from devboard.services.conversation_service import ConversationService
from devboard.services.global_context_service import GlobalContextService
from devboard.services.project_service import ProjectService
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_service import TaskService

_VISUAL_CONTENT_SECTION = """\
## VISUAL CONTENT

The frontend renders these fenced code blocks as live visuals in both conversation messages
and documents:

- **` ```mermaid `** — interactive diagrams for architecture, data flows, state machines,
  or sequences
- **` ```html `** / **` ```svg `** — sandboxed live previews (scripts enabled) for UI mockups,
  styled components, or interactive demos
- **` ```html `** blocks can also load external JS libraries from CDNs (e.g. Chart.js, D3.js,
  Plotly) for rich dashboards, charts, or interactive data tables — provide a complete
  self-contained HTML document

Use these proactively: diagrams in conversation to explain ideas, visual mockups mid-discussion
rather than waiting for a formal spec update, dashboards to summarise project status."""

_BEHAVIOUR_GUIDELINES_SECTION = """\
## BEHAVIOUR GUIDELINES

- **Confirm before editing** — only modify the project or initiative document when explicitly
  instructed or after asking and receiving confirmation.
- **Discuss first** — when a user raises a change, ask clarifying questions to reach mutual
  understanding before proposing an update.
- **After editing** — briefly note what changed and invite feedback; do not repeat the full
  document content.
- **Be accurate and honest** — base responses on provided context; acknowledge when context is
  insufficient rather than speculating.
- **Be concise** — use Markdown formatting, short paragraphs, and bullets. Avoid walls of text."""

_TASK_CREATION_SECTION = """\
## TASK CREATION

When creating tasks with specifications, ensure specs include: goal (what and why), relevant background, functional requirements and constraints. May include critical implementation details essential to the outcome (e.g. specific data models, API contracts). Exclude routine implementation steps. Keep specs concise and scannable — use bullet points, tables, and diagrams."""

PROJECT_ROLE_PROMPT = f"""\
You are a Project Assistant for DevBoard, an AI-powered developer command center.
You help manage a top-level **project** — a container for related development work with its own
specification document, tasks, and child initiatives.

## PROJECT SPECIFICATION

The project specification is a living reference document shared as context with every task agent
in the project. It gives agents (and human reviewers) rapid orientation —
keep it accurate and concise, not exhaustive.

**Recommended structure:**

### Overview
What the project is, its goals, and target users.

### Technical Architecture
Tech stack, key components, infrastructure, and integration points.

### Key Decisions & Constraints
Design decisions already settled, important trade-offs, and non-obvious rules.

### Current State
What has been built and where things stand. Keep this up-to-date as work progresses.

When proposing updates to the specification, follow this structure. Use visual content
(diagrams, tables) where it reduces ambiguity — see **VISUAL CONTENT** below.

## INITIATIVES

An initiative is a sub-project with its own scoped goal, context document, and tasks. Outcomes
from an initiative feed back into this project's specification.

**When to propose creating one:**
- The user describes a body of work spanning 3 or more related tasks with a clear sub-goal.
- An investigation or discovery phase is likely to generate structured follow-up work.

**How:** Use `create_initiative` to create one. After creating, help the user set up its context
document using `set_initiative_context_content`. To view or edit an existing initiative's context,
use `view_initiative_details`, `edit_initiative_context`, or `set_initiative_context_content`.
When an initiative is complete, use `complete_initiative`.

## LIFECYCLE

When all active tasks and initiatives are complete with no obvious follow-ups, proactively ask the
user: create follow-up work, or mark this project as complete? Use `complete_project` to finalise.

{_VISUAL_CONTENT_SECTION}

{_BEHAVIOUR_GUIDELINES_SECTION}

{_TASK_CREATION_SECTION}
"""

_INITIAL_SETUP_GUIDANCE = """\
NO SPECIFICATION EXISTS YET.

Your first priority is to help the user create one. The project specification is a shared \
reference document used as context by every task agent in this project — it gives them rapid \
orientation without needing to re-discover project basics each time.

Recommended structure: Overview / Technical Architecture / Key Decisions & Constraints / \
Current State.

To get started, ask the user focused questions covering:
- What is this project and what problem does it solve? Who are the users?
- What is the tech stack and high-level architecture?
- Any key design decisions or constraints already in place?
- Is this brand new or is work already in progress?

Keep it conversational — don't ask everything at once. Draft from their answers and confirm \
before saving.\
"""

_TASK_TABLE_HEADER = "ID|Status|Title|Created"


def _format_task_summary_row(task: Task) -> str:
    created = task.created_at.strftime("%Y-%m-%d")
    return f"{task.id}|{task.status.value}|{task.title}|{created}"


def _format_task_table(tasks: list[Task]) -> str:
    rows = "\n".join(_format_task_summary_row(t) for t in tasks)
    return f"{_TASK_TABLE_HEADER}\n{rows}"


def _format_initiatives_section(project: Project) -> str:
    """Format the initiatives summary table for a project."""
    if not project.initiatives:
        return ""
    header = "ID|Name|Status|Tasks"
    rows = []
    for initiative in project.initiatives:
        status = "complete" if initiative.complete else "active"
        task_count = len(initiative.tasks)
        rows.append(f"{initiative.id}|{initiative.name}|{status}|{task_count}")
    return f"INITIATIVES:\n{header}\n" + "\n".join(rows) + "\n"


def build_project_context(
    project: Project,
    active_tasks: list[Task],
    recent_completed_tasks: list[Task],
    *,
    global_context: str | None = None,
) -> str:
    spec_content = project.specification.content or _INITIAL_SETUP_GUIDANCE
    global_context_section = f"# Global Context\n<document>\n{global_context}\n</document>\n" if global_context else ""

    context = f"""
{global_context_section}PROJECT: {project.name} (ID: {project.id})

PROJECT SPECIFICATION DOCUMENT:
<document>
{spec_content}
</document>
"""

    if active_tasks:
        context += f"\nACTIVE TASKS:\n{_format_task_table(active_tasks)}\n"

    if recent_completed_tasks:
        context += f"\nRECENTLY COMPLETED TASKS:\n{_format_task_table(recent_completed_tasks)}\n"

    initiatives_section = _format_initiatives_section(project)
    if initiatives_section:
        context += f"\n{initiatives_section}"

    return context


class ProjectAgentRole(AgentRole):
    """Role for project agents — manages specification, tasks, and lifecycle."""

    def __init__(
        self,
        project: Project,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
        task_service: TaskService,
        project_service: ProjectService,
        conversation_repo: ConversationRepository,
        conversation_id: int | None,
        conversation_service: ConversationService | None = None,
    ):
        self.project = project
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service
        self.task_service = task_service
        self.project_service = project_service
        self.conversation_repo = conversation_repo
        self.conversation_id = conversation_id
        self.conversation_service = conversation_service

    @property
    def event_context_types(self) -> list[str]:
        return [
            "task.created",
            "task.merged",
            "task.deleted",
            "document.updated",
            "project.updated",
            "project.completed",
        ]

    def get_system_prompt(self) -> str:
        return PROJECT_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        log_entry_repo = LogEntryRepository(self.document_repository.db)
        event_emitter = SystemEventEmitter(log_entry_repo)
        initiative_repo = InitiativeRepository(self.conversation_repo.db)

        tools: list[Tool] = [
            # Project specification editing tools (bound directly to the project's spec document)
            create_set_document_content_tool(
                self.project.specification,
                self.document_repository,
                document_parent=self.project,
                system_event_emitter=event_emitter,
            ),
            create_document_edit_tool(
                self.project.specification,
                self.document_repository,
                document_parent=self.project,
                system_event_emitter=event_emitter,
            ),
            # Task query tools
            create_list_tasks_tool(self.project, self.task_service),
            create_view_task_details_tool(self.project, self.task_service, self.conversation_repo),
            create_create_task_tool(self.project, self.task_service, self.agent_config_service, self.conversation_repo),
            create_edit_task_tool(self.project, self.task_service, self.document_repository),
            # Task agent coordination tools
            create_send_task_agent_prompt_tool(self.project, self.task_service, self.conversation_repo),
            create_get_task_agent_status_tool(self.project, self.task_service, self.conversation_repo),
            # Conversation analysis tool
            create_inspect_conversation_tool(self.conversation_repo),
            # Project lifecycle tool
            create_complete_project_tool(self.project, self.project_service),
            # Initiative management tools
            create_create_initiative_tool(self.project, self.project_service),
            create_list_project_initiatives_tool(self.project, initiative_repo),
            create_view_initiative_details_tool(self.project, initiative_repo),
            create_edit_initiative_context_tool(self.project, initiative_repo, self.document_repository),
            create_set_initiative_context_content_tool(self.project, initiative_repo, self.document_repository),
            create_complete_initiative_tool(self.project, initiative_repo, self.project_service),
        ]

        # Context management tools (refocus/branch) require a conversation_id and service
        if self.conversation_id is not None and self.conversation_service is not None:
            conversation = self.conversation_repo.get_by_id(self.conversation_id)
            if conversation is not None:
                tools.extend(
                    [
                        create_refocus_conversation_tool(
                            conversation, self.conversation_service, self.conversation_repo
                        ),
                        create_branch_conversation_tool(conversation, self.conversation_service),
                    ]
                )

        # Add codebase tools if project has codebases
        if self.project.codebases:
            codebase_repo = CodebaseRepository(self.conversation_repo.db)
            tools.extend(
                [
                    create_view_codebase_details_tool(self.project.codebases, codebase_repo),
                    create_update_codebase_tool(self.project.codebases, codebase_repo),
                    create_multi_codebase_investigation_tool(
                        [
                            CodebaseInvestigationContext(codebase=cb, working_dir=cb.local_path)
                            for cb in self.project.codebases
                        ],
                        self.agent_config_service,
                        conversation_repo=self.conversation_repo,
                        parent_entity=self.project,
                        parent_conversation_id=self.conversation_id,
                        execution_manager=get_execution_manager(),
                    ),
                ]
            )

        return tools

    async def get_context_content(self) -> str:
        gc = GlobalContextService().get().content or None
        active_tasks, recent_completed = self.task_service.get_project_task_summaries(self.project.id)
        return build_project_context(self.project, active_tasks, recent_completed, global_context=gc)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role."""
        return [
            "Read",
            "Grep",
            "Glob",
            "Bash",
            "WebFetch",
            "WebSearch",
            "TaskCreate",
            "TaskGet",
            "TaskUpdate",
            "TaskList",
            "Agent",
            "Skill",
            "TodoWrite",
        ]
