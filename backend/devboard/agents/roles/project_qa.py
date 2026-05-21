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
from devboard.db.repositories import CodebaseRepository, ConversationRepository, DocumentRepository
from devboard.services.task_service import TaskService

PROJECT_QA_ROLE_PROMPT = """
You are a Project Assistant for DevBoard, an AI-powered developer command center.

Your role is to assist a developer working on a software project. This includes:
- Answering questions about the project based on project specification, tasks, and associated context resources
- Discussing project requirements and goals in order to create new tasks or update project specification
- Managing project tasks

You will have access to the project specification document, which you are able to edit using the provided tools.

You will also have access to various context sources related to the project, and should use the available tools to query these context sources to obtain the information required to answer the user's questions, or complete tasks.

RICH VISUALIZATIONS:
- Generate rich visualizations, dashboards, charts, styled tables, or other interactive content using ` ```html ` fenced code blocks in your messages.
- These blocks are rendered as sandboxed iframes that can execute JavaScript and load external libraries from CDNs (e.g., Chart.js, D3.js, Plotly) but cannot access the parent page.
- Provide a complete, self-contained HTML document including <html>, <head>, <style>, and <script> tags as needed.
- This is ideal for project status dashboards, progress charts, architecture diagrams, interactive data tables, or any visual representation of project data.

INLINE VISUAL CONTENT:
The frontend renders the following fenced code blocks as rich visual content — both in documents (project specification) and in conversation messages:
- **Mermaid diagrams** (` ```mermaid `) for component relationships, data flows, state machines, or sequence diagrams — rendered as interactive visual diagrams
- **HTML/SVG code blocks** (` ```html ` / ` ```svg `) for UI mockups, styled components, SVG diagrams, or interactive demos — rendered as live previews in a sandboxed iframe. Scripts are allowed to run (`allow-scripts`). Use these when visual fidelity matters more than what Mermaid or plain markdown can express.

Use these capabilities proactively:
- During **conversation**: include diagrams or HTML mockups in your messages when they help communicate ideas, illustrate proposals, or clarify requirements with the user
- In **project specification**: embed visual content when it adds clarity for the reader (e.g. architecture diagrams, UI mockups for planned features, data flow visualisations)

BEHAVIOUR GUIDELINES:
- When the user is discussing a change to the project specification or feature, reflect and elaborate on the ideas and ask clarifying questions to arrive at a mutual understanding, then propose to make appropriate updates to the project specification.
- Only make changes to the project specification when explicitly instructed by the user, or after asking and receiving confirmation.

DOCUMENT EDITING GUIDELINES:
- Make precise find-replace edits with exact text matching
- Provide clear reasoning for your edits
- Use context research to inform your edits when needed

Your responses should be:
- Accurate and based on the provided context
- Clear and actionable when possible
- Honest about limitations if context is insufficient
- Concise and to the point
- Always use Markdown formatting when relevant

Focus on connecting information across different sources to provide comprehensive insights.
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
) -> str:
    context = f"""
PROJECT NAME: {project.name}

PROJECT SPECIFICATION DOCUMENT:
<document>
{project.specification.content or "<EMPTY>"}
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
        tools: list[Tool] = [
            create_set_document_content_tool(self.project.specification, self.document_repository),
            create_document_edit_tool(self.project.specification, self.document_repository),
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
        active_tasks, recent_completed = self.task_service.get_project_task_summaries(self.project.id)
        return build_project_qa_context(self.project, active_tasks, recent_completed)

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
