"""Task Planning Agent using PydanticAI for interactive document crafting with deferred tools."""

from abc import ABCMeta

from pydantic_ai import Tool
from pydantic_ai.tools import ToolFuncEither

from devboard.agents.engines.internal.base_agent import InternalAgent
from devboard.agents.engines.internal.deps import BaseDeps
from devboard.agents.engines.internal.tools import (
    create_code_structure_search_tool,
    create_directory_tree_tool,
    create_document_edit_tool,
    create_file_search_tool,
    create_set_document_content_tool,
    create_text_search_tool,
)
from devboard.agents.language_models import LanguageModel
from devboard.agents.roles.task_planning import PLANNING_ROLE_PROMPT, build_task_planning_context
from devboard.agents.roles.task_specification import SPECIFICATION_ROLE_PROMPT, build_task_specification_context
from devboard.agents.roles.types import AgentRole
from devboard.db.models import Task
from devboard.db.repositories import DocumentRepository
from devboard.integrations.codebase import CodebaseIntegration


class InternalTaskAgent(InternalAgent[BaseDeps], metaclass=ABCMeta):
    """Base class for task-related agents."""

    deps_type = BaseDeps

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        context_service,
        model: LanguageModel,
    ):
        self.task = task
        self.document_repository = document_repository
        # Create CodebaseIntegration if task has an associated codebase
        self.codebase_integration = CodebaseIntegration(task.codebase.local_path) if task.codebase else None
        super().__init__(
            context_service=context_service,
            model=model,
        )


class TaskSpecificationAgent(InternalTaskAgent):
    """Service for task planning using AI with deferred document editing tools."""

    agent_role = AgentRole.TASK_SPECIFICATION

    async def _get_context_message_content(self, deps: BaseDeps) -> str:
        """Construct the first user message that contains context information for the agent."""
        return build_task_specification_context(self.task)

    def _get_role_prompt(self) -> str:
        """Get default system prompt (used for base agent creation)."""
        return SPECIFICATION_ROLE_PROMPT

    def _get_tools(self) -> list[Tool | ToolFuncEither]:
        tools: list[Tool | ToolFuncEither] = []

        # Always provide both set_content and edit tools for specification
        tools.extend([
            create_set_document_content_tool(
                document=self.task.specification, document_repo=self.document_repository
            ),
            create_document_edit_tool(document=self.task.specification, document_repo=self.document_repository)
        ])

        # Add codebase search tools if codebase is available (may move to dedicated Codebase investigation agent later)
        if self.codebase_integration:
            tools.extend(
                [
                    create_text_search_tool(self.codebase_integration),
                    create_file_search_tool(self.codebase_integration),
                    create_code_structure_search_tool(self.codebase_integration),
                    create_directory_tree_tool(self.codebase_integration),
                ]
            )

        return tools


class TaskPlanningAgent(InternalTaskAgent):
    """Service for task planning using AI with deferred document editing tools."""

    agent_role = AgentRole.TASK_PLANNING

    async def _get_context_message_content(self, deps: BaseDeps) -> str:
        """Construct the first user message that contains context information for the agent."""
        return build_task_planning_context(self.task)

    def _get_role_prompt(self) -> str:
        """Get default system prompt (used for base agent creation)."""
        return PLANNING_ROLE_PROMPT

    def _get_tools(self) -> list[Tool | ToolFuncEither]:
        tools: list[Tool | ToolFuncEither] = []

        # Always provide both set_content and edit tools for both documents
        tools.extend([
            create_set_document_content_tool(
                document=self.task.specification, document_repo=self.document_repository
            ),
            create_document_edit_tool(document=self.task.specification, document_repo=self.document_repository),
            create_set_document_content_tool(
                document=self.task.implementation_plan, document_repo=self.document_repository
            ),
            create_document_edit_tool(
                document=self.task.implementation_plan, document_repo=self.document_repository
            )
        ])

        # Add codebase search tools if codebase is available (may move to dedicated Codebase investigation agent later)
        if self.codebase_integration:
            tools.extend(
                [
                    create_text_search_tool(self.codebase_integration),
                    create_file_search_tool(self.codebase_integration),
                    create_code_structure_search_tool(self.codebase_integration),
                    create_directory_tree_tool(self.codebase_integration),
                ]
            )

        return tools
