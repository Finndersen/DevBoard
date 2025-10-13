"""Task Planning Agent using PydanticAI for interactive document crafting with deferred tools."""

import logging
from abc import ABCMeta
from enum import Enum

from pydantic_ai import Tool
from pydantic_ai.tools import ToolFuncEither

from devboard.agents.engines.internal.base_agent import InternalAgent
from devboard.agents.engines.internal.deps import BaseDeps
from devboard.agents.engines.internal.tools import create_document_edit_tool, create_set_document_content_tool
from devboard.agents.roles.task_planning import PLANNING_SYSTEM_PROMPT
from devboard.agents.roles.task_specification import SPECIFICATION_SYSTEM_PROMPT
from devboard.agents.roles.types import AgentRole
from devboard.db.models import Task
from devboard.db.repositories import DocumentRepository

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """Task states that support document crafting."""

    DESIGNING = "Designing"
    PLANNING = "Planning"


class DocumentType(str, Enum):
    """Document types that can be edited."""

    SPECIFICATION = "specification"
    IMPLEMENTATION_PLAN = "implementation_plan"


class InternalTaskAgent(InternalAgent[BaseDeps], metaclass=ABCMeta):
    """Base class for task-related agents."""

    deps_type = BaseDeps

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        context_service,
        model_name: str,
    ):
        self.task = task
        self.document_repository = document_repository
        super().__init__(
            context_service=context_service,
            model_name=model_name,
        )


class TaskSpecificationAgent(InternalTaskAgent):
    """Service for task planning using AI with deferred document editing tools."""

    agent_role = AgentRole.TASK_SPECIFICATION

    async def _get_context_message_content(self, deps: BaseDeps) -> str:
        """Construct the first user message that contains context information for the agent."""
        context_message = f"""
        TASK NAME: {self.task.title}
        TASK STATE: {self.task.status.value}
        TASK SPECIFICATION DOCUMENT (Dynamically updated live state):
        ```markdown
        {self.task.specification.content or "<EMPTY>"}
        ```
        """
        return context_message

    def _get_system_prompt(self) -> str:
        """Get default system prompt (used for base agent creation)."""
        return SPECIFICATION_SYSTEM_PROMPT

    def _get_tools(self) -> list[Tool | ToolFuncEither]:
        # Use set_content tool if document is blank, otherwise use edit tool
        if not self.task.specification.content or not self.task.specification.content.strip():
            return [
                create_set_document_content_tool(
                    document=self.task.specification, document_repo=self.document_repository
                )
            ]
        else:
            return [create_document_edit_tool(document=self.task.specification, document_repo=self.document_repository)]


class TaskPlanningAgent(InternalTaskAgent):
    """Service for task planning using AI with deferred document editing tools."""

    agent_role = AgentRole.TASK_PLANNING

    async def _get_context_message_content(self, deps: BaseDeps) -> str:
        """Construct the first user message that contains context information for the agent."""
        context_message = f"""
        TASK SPECIFICATION DOCUMENT:
        ```markdown
        {self.task.specification.content}
        ```

        TASK IMPLEMENTATION PLAN DOCUMENT:
        ```markdown
        {self.task.implementation_plan.content}
        ```
        """
        return context_message

    def _get_system_prompt(self) -> str:
        """Get default system prompt (used for base agent creation)."""
        return PLANNING_SYSTEM_PROMPT

    def _get_tools(self) -> list[Tool | ToolFuncEither]:
        tools: list[Tool | ToolFuncEither] = []

        # Add appropriate tool for specification document
        if not self.task.specification.content.strip():
            tools.append(
                create_set_document_content_tool(
                    document=self.task.specification, document_repo=self.document_repository
                )
            )
        else:
            tools.append(
                create_document_edit_tool(document=self.task.specification, document_repo=self.document_repository)
            )

        # Add appropriate tool for implementation plan document
        if not self.task.implementation_plan.content.strip():
            tools.append(
                create_set_document_content_tool(
                    document=self.task.implementation_plan, document_repo=self.document_repository
                )
            )
        else:
            tools.append(
                create_document_edit_tool(
                    document=self.task.implementation_plan, document_repo=self.document_repository
                )
            )

        return tools
