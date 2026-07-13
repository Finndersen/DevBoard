"""Role for managing tasks in MERGED state (post-merge finalisation)."""

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.context_helpers import build_task_context
from devboard.agents.roles.task_base import TaskAgentRoleBase
from devboard.agents.tools import build_project_context_document_tools
from devboard.db.models import Task
from devboard.db.repositories import ConversationRepository, DocumentRepository, LogEntryRepository
from devboard.services.global_context_service import GlobalContextService
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_service import TaskService

TASK_FINALISATION_ROLE_PROMPT = """
You are a Task Finalisation Assistant for DevBoard, helping a developer complete post-merge housekeeping after code has been merged.

Your role is to:
1. REVIEW: Read the task specification and change summary to understand what was built
2. PLAN: Propose a structured plan of all intended follow-up actions:
   - Updates to the relevant project/initiative context (see below)
   - Any updates needed to external resources (Jira, documentation, etc.)
   - Any follow-up tasks to create
3. GET CONFIRMATION: Present your proposed plan to the user and wait for their explicit approval before taking any action
4. EXECUTE: Once the user approves, use the available tools to implement the plan:
   - Use the project/initiative context editing tool(s) to update the relevant document (see below).
   - Use `create_task` to create any follow-up tasks
   - Use other tools to update external resources as needed

UPDATING PROJECT / INITIATIVE CONTEXT:
Your context shows the project (and initiative if applicable), and your tools are already bound to
the correct documents — you never pass a project or document id.
- If the task belongs to a **project with no initiative** (the context shows only a "# Project" section),
  you have `edit_project_specification` for that project's specification.
- If the task belongs to an **initiative** (the context shows both a "# Project" and an "# Initiative"
  section), you have `edit_initiative_context` for the initiative's own document and
  `edit_project_specification` for the parent project's specification. Update whichever the merged work
  affects, feeding outcomes and key decisions up into the parent project only when they change its scope.

IMPORTANT:
- The code has already been merged — do not attempt to modify the codebase
- Do not take any action without first proposing a plan and receiving user approval
- Focus on keeping project and initiative context accurate and up-to-date so future tasks have correct information
- Be concise and targeted in spec updates — only change what the merged work actually affects
- The user will manually archive the task using the Archive Task button when satisfied with the results
"""


class TaskFinalisationAgentRole(TaskAgentRoleBase):
    """Role for managing tasks in MERGED state."""

    def __init__(
        self,
        task: Task,
        task_service: TaskService,
        working_dir: str,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
        conversation_id: int | None,
        document_repo: DocumentRepository,
    ):
        super().__init__(
            task=task,
            task_service=task_service,
            conversation_repo=conversation_repo,
            conversation_id=conversation_id,
            agent_config_service=agent_config_service,
            working_dir=working_dir,
        )
        self.document_repo = document_repo

    def get_system_prompt(self) -> str:
        return TASK_FINALISATION_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        tools = super().get_tools()
        event_emitter = SystemEventEmitter(LogEntryRepository(self.document_repo.db))
        # Always add project specification edit tool
        tools.extend(
            build_project_context_document_tools(
                self.task.project,
                self.document_repo,
                system_event_emitter=event_emitter,
            )
        )
        # If task belongs to an initiative, also add initiative context edit tool
        if self.task.initiative is not None and self.task.initiative.specification is not None:
            from devboard.agents.tools.document_editing import create_document_edit_tool

            tools.append(
                create_document_edit_tool(
                    self.task.initiative.specification,
                    self.document_repo,
                    document_parent=self.task.initiative,
                    system_event_emitter=event_emitter,
                )
            )
        return tools

    async def get_context_content(self) -> str:
        gc = GlobalContextService().get().content or None
        return build_task_context(
            self.task, working_dir=self.working_dir, include_step_outcomes=True, global_context=gc
        )

    @property
    def allowed_builtin_tools(self) -> list[str]:
        return ["Read", "Grep", "Glob", "WebFetch", "WebSearch"]

    @property
    def include_builtin_system_prompt(self) -> bool:
        return False
