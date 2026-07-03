"""Project Q&A role for answering questions and managing project specifications."""

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.roles.base import AgentRole
from devboard.agents.tools import (
    create_document_edit_tool,
    create_inspect_conversation_tool,
    create_set_document_content_tool,
)
from devboard.agents.tools.codebase_management_tools import (
    create_update_codebase_tool,
    create_view_codebase_details_tool,
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
from devboard.db.repositories import CodebaseRepository, ConversationRepository, DocumentRepository, LogEntryRepository
from devboard.services.global_context_service import GlobalContextService
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_service import TaskService

PROJECT_QA_ROLE_PROMPT = """
You are a Project Assistant for DevBoard, an AI-powered developer command center.

Your role is to assist a developer working on a software project by:
- Answering questions about the project based on the specification, tasks, and associated context
- Discussing requirements and goals to create new tasks or refine the project specification
- Managing project tasks

## PROJECT SPECIFICATION

The project specification is a living reference document shared as context with every task agent
in the project. It gives task agents (and human reviewers) rapid orientation — keep it accurate
and concise, not exhaustive.

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
rather than waiting for a formal spec update, dashboards to summarise project status.

## BEHAVIOUR GUIDELINES

- **Confirm before editing** — only modify the project specification when explicitly instructed
  or after asking and receiving confirmation.
- **Discuss first** — when a user raises a change, ask clarifying questions to reach mutual
  understanding before proposing a specification update.
- **After editing** — briefly note what changed and invite feedback; do not repeat the full
  document content.
- **Be accurate and honest** — base responses on provided context; acknowledge when context is
  insufficient rather than speculating.
- **Be concise** — use Markdown formatting, short paragraphs, and bullets. Avoid walls of text.
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


def build_project_qa_context(
    project: Project,
    active_tasks: list[Task],
    recent_completed_tasks: list[Task],
    *,
    global_context: str | None = None,
) -> str:
    spec_content = project.specification.content or _INITIAL_SETUP_GUIDANCE
    global_context_section = f"# Global Context\n<document>\n{global_context}\n</document>\n" if global_context else ""
    context = f"""
{global_context_section}PROJECT NAME: {project.name}

PROJECT SPECIFICATION DOCUMENT:
<document>
{spec_content}
</document>
"""
    if active_tasks:
        context += f"\nACTIVE TASKS:\n{_format_task_table(active_tasks)}\n"

    if recent_completed_tasks:
        context += f"\nRECENTLY COMPLETED TASKS:\n{_format_task_table(recent_completed_tasks)}\n"

    return context


class ProjectQAAgentRole(AgentRole):
    """Role for project Q&A and specification management."""

    def __init__(
        self,
        project: Project,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
        task_service: TaskService,
        conversation_repo: ConversationRepository,
        conversation_id: int | None,
    ):
        self.project = project
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service
        self.task_service = task_service
        self.conversation_repo = conversation_repo
        self.conversation_id = conversation_id

    def get_system_prompt(self) -> str:
        """Get the system prompt for project Q&A role."""
        return PROJECT_QA_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for project Q&A role.

        Returns:
            List of document editing tools, task query tools, and codebase investigation tool
        """
        log_entry_repo = LogEntryRepository(self.document_repository.db)
        event_emitter = SystemEventEmitter(log_entry_repo)

        tools: list[Tool] = [
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
        ]

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
        """Get context content for project Q&A role.

        Returns:
            Formatted context containing project details, specification, and task summaries
        """
        gc = GlobalContextService().get().content or None
        active_tasks, recent_completed = self.task_service.get_project_task_summaries(self.project.id)
        return build_project_qa_context(self.project, active_tasks, recent_completed, global_context=gc)

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
