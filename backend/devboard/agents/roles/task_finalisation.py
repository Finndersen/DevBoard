"""Role for managing tasks in MERGED state (post-merge finalisation)."""

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.context_helpers import build_task_context
from devboard.agents.roles.task_base import TaskAgentRoleBase
from devboard.agents.tools import create_edit_project_specification_tool
from devboard.agents.tools.task_completion_tools import create_finalise_task_tool
from devboard.db.models import Task
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.services.task_service import TaskService

TASK_FINALISATION_ROLE_PROMPT = """
You are a Task Finalisation Assistant for DevBoard, helping a developer complete post-merge housekeeping after code has been merged.

Your role is to:
1. REVIEW: Read the task specification and change summary to understand what was built
2. UPDATE PROJECT SPEC: Use `edit_project_specification` to update the project specification with any new information, changed architecture, or updated context that the merged changes introduced
3. UPDATE EXTERNAL DOCS: If the task involves Jira issues, external documentation, or other external resources, suggest or perform the appropriate updates
4. FOLLOW-UP TASKS: Use `create_task` to create any follow-up tasks identified during the work (known limitations, deferred improvements, discovered issues)
5. FINALISE: Once all housekeeping is complete, call `finalise_task` to archive the task as COMPLETE

IMPORTANT:
- The code has already been merged — do not attempt to modify the codebase
- Focus on keeping project context accurate and up-to-date so future tasks have correct information
- Be concise and targeted in spec updates — only change what the merged work actually affects
- After completing all housekeeping, always call `finalise_task` to complete the workflow
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
        project_repo = ProjectRepository(self.conversation_repo.db)
        tools = super().get_tools()
        tools.extend(
            [
                create_edit_project_specification_tool(project_repo, self.document_repo),
                create_finalise_task_tool(self.task, self.task_service),
            ]
        )
        return tools

    async def get_context_content(self) -> str:
        return build_task_context(self.task, working_dir=self.working_dir, include_step_outcomes=True)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        return ["Read", "Grep", "Glob", "WebFetch", "WebSearch"]

    @property
    def include_builtin_system_prompt(self) -> bool:
        return False
