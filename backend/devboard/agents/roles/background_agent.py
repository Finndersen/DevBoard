"""Background agent role for evaluation and analysis of conversations, agents, and tasks."""

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.base import AgentRole
from devboard.agents.tools import (
    create_inspect_conversation_tool,
    create_list_conversations_tool,
    create_list_tasks_tool,
    create_view_agent_config_tool,
    create_view_conversation_content_tool,
    create_view_conversation_details_tool,
    create_view_task_details_tool,
)
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.db.repositories.codebase import CodebaseRepository
from devboard.services.integration_service import IntegrationService
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
    ):
        if not system_prompt:
            raise ValueError("system_prompt cannot be empty")
        self.system_prompt = system_prompt
        self.task_service = task_service
        self.conversation_repo = conversation_repo
        self.document_repo = document_repo
        self.agent_config_service = agent_config_service
        self.integration_service = integration_service
        self.codebase_repo = CodebaseRepository(conversation_repo.db)

    def get_system_prompt(self) -> str:
        return self.system_prompt

    def get_tools(self) -> list[Tool]:
        return [
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
        ]

    async def get_context_content(self) -> str:
        return "You are a background agent. Use the available tools to investigate conversations, agents, and tasks."
