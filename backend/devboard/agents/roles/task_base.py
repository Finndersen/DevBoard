"""Abstract base class for task agent roles."""

from abc import abstractmethod

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.roles.base import AgentRole
from devboard.agents.tools import create_list_tasks_tool, create_view_task_details_tool
from devboard.agents.tools.codebase_management_tools import (
    create_update_codebase_tool,
    create_view_codebase_details_tool,
)
from devboard.agents.tools.sub_agent_tools import create_task_codebase_investigation_tool
from devboard.agents.tools.task_tools import create_create_task_tool
from devboard.db.models import Task
from devboard.db.repositories import CodebaseRepository, ConversationRepository
from devboard.services.task_service import TaskService


class TaskAgentRoleBase(AgentRole):
    """Abstract base class for task agent roles.

    Consolidates shared constructor parameters and common tools
    (list_tasks, view_task_details, create_task, investigate_codebase)
    across TaskPlanningAgentRole, TaskImplementationAgentRole, and TaskPRReviewAgentRole.
    """

    def __init__(
        self,
        task: Task,
        task_service: TaskService,
        conversation_repo: ConversationRepository,
        conversation_id: int | None,
        agent_config_service: AgentConfigService,
        working_dir: str,
    ):
        self.task = task
        self.task_service = task_service
        self.conversation_repo = conversation_repo
        self.conversation_id = conversation_id
        self.agent_config_service = agent_config_service
        self.working_dir = working_dir

    def get_tools(self) -> list[Tool]:
        """Return common tools available to all task agent roles.

        Subclasses should call super().get_tools() and extend with role-specific tools.
        """
        codebase_repo = CodebaseRepository(self.conversation_repo.db)
        codebases = [self.task.codebase]
        return [
            create_list_tasks_tool(self.task.project, self.task_service),
            create_view_task_details_tool(self.task.project, self.task_service),
            create_create_task_tool(self.task.project, self.task_service, self.conversation_repo),
            create_task_codebase_investigation_tool(
                self.task,
                self.agent_config_service,
                conversation_repo=self.conversation_repo,
                parent_conversation_id=self.conversation_id,
                working_dir=self.working_dir,
                execution_manager=get_execution_manager(),
            ),
            create_view_codebase_details_tool(codebases, codebase_repo),
            create_update_codebase_tool(codebases, codebase_repo),
        ]

    @abstractmethod
    def get_system_prompt(self) -> str:
        pass

    @abstractmethod
    async def get_context_content(self) -> str:
        pass
