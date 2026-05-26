"""Background agent role for evaluation and analysis of conversations, agents, and tasks."""

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.roles.base import AgentRole
from devboard.agents.tools import (
    create_edit_project_specification_tool,
    create_inspect_conversation_tool,
    create_list_conversations_tool,
    create_list_projects_tool,
    create_list_tasks_tool,
    create_set_project_specification_content_tool,
    create_view_agent_config_tool,
    create_view_conversation_content_tool,
    create_view_conversation_details_tool,
    create_view_project_details_tool,
    create_view_task_details_tool,
)
from devboard.agents.tools.background_agent_tools import (
    create_query_agent_runs_tool,
    create_read_agent_state_tool,
    create_read_state_tool,
    create_update_state_tool,
)
from devboard.agents.tools.codebase_management_tools import create_view_codebase_details_tool
from devboard.agents.tools.event_tools import (
    create_create_event_tool,
    create_query_events_tool,
)
from devboard.agents.tools.sub_agent_tools import (
    CodebaseInvestigationContext,
    create_multi_codebase_investigation_tool,
)
from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.repositories import (
    BackgroundAgentRepository,
    BackgroundAgentRunRepository,
    ConversationRepository,
    DocumentRepository,
)
from devboard.db.repositories.codebase import CodebaseRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.services.integration_service import IntegrationService
from devboard.services.log_entry_service import LogEntryService
from devboard.services.task_service import TaskService


class BackgroundAgentRole(AgentRole):
    """Role for background agents that evaluate and analyse conversations, agents, and tasks."""

    def __init__(
        self,
        system_prompt: str,
        task_service: TaskService,
        conversation_repo: ConversationRepository,
        document_repo: DocumentRepository,
        agent_config_service: AgentConfigService,
        integration_service: IntegrationService,
        project_repo: ProjectRepository,
        codebase_repo: CodebaseRepository,
        background_agent: BackgroundAgent,
        conversation_id: int | None,
        log_entry_service: LogEntryService,
        background_agent_repo: BackgroundAgentRepository,
        agent_run_repo: BackgroundAgentRunRepository,
    ):
        if not system_prompt:
            raise ValueError("system_prompt cannot be empty")
        self.system_prompt = system_prompt
        self.task_service = task_service
        self.conversation_repo = conversation_repo
        self.document_repo = document_repo
        self.agent_config_service = agent_config_service
        self.integration_service = integration_service
        self.project_repo = project_repo
        self.codebase_repo = codebase_repo
        self.background_agent = background_agent
        self.conversation_id = conversation_id
        self.log_entry_service = log_entry_service
        self.background_agent_repo = background_agent_repo
        self.agent_run_repo = agent_run_repo

    def get_system_prompt(self) -> str:
        return self.system_prompt

    def get_tools(self) -> list[Tool]:
        tools: list[Tool] = [
            create_list_conversations_tool(self.conversation_repo),
            create_view_conversation_details_tool(self.conversation_repo),
            create_view_conversation_content_tool(self.conversation_repo),
            create_inspect_conversation_tool(self.conversation_repo),
            create_view_agent_config_tool(
                self.conversation_repo,
                self.document_repo,
                self.agent_config_service,
                self.integration_service,
                self.task_service,
            ),
            create_list_tasks_tool(None, self.task_service, codebase_repo=self.codebase_repo),
            create_view_task_details_tool(None, self.task_service, self.conversation_repo),
            # Project tools
            create_list_projects_tool(self.project_repo),
            create_view_project_details_tool(self.project_repo, self.task_service),
            create_edit_project_specification_tool(self.project_repo, self.document_repo),
            create_set_project_specification_content_tool(self.project_repo, self.document_repo),
            # Event tools
            create_query_events_tool(self.log_entry_service, self.background_agent),
            create_create_event_tool(
                self.log_entry_service,
                self.background_agent,
                self.agent_run_repo,
                self.conversation_id,
            ),
            # State tools
            create_read_state_tool(self.background_agent),
            create_update_state_tool(self.background_agent_repo, self.background_agent),
            create_read_agent_state_tool(self.background_agent_repo),
            # Agent run tools
            create_query_agent_runs_tool(self.agent_run_repo, self.background_agent),
        ]

        codebases = self.codebase_repo.get_all()
        if codebases:
            tools.extend(
                [
                    create_view_codebase_details_tool(codebases, self.codebase_repo),
                    create_multi_codebase_investigation_tool(
                        [CodebaseInvestigationContext(codebase=cb, working_dir=cb.local_path) for cb in codebases],
                        self.agent_config_service,
                        conversation_repo=self.conversation_repo,
                        parent_entity=self.background_agent,
                        parent_conversation_id=self.conversation_id,
                        execution_manager=get_execution_manager(),
                    ),
                ]
            )

        return tools

    async def get_context_content(self) -> str:
        return "You are a background agent. Use the available tools to investigate conversations, agents, and tasks."
