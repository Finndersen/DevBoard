"""Task Planning Agent using PydanticAI for interactive document crafting with deferred tools."""

import logging
from abc import ABCMeta
from enum import Enum

from pydantic_ai import Tool
from pydantic_ai.tools import ToolFuncEither

from devboard.agents.base_agent import BaseAgent
from devboard.agents.deps import BaseDeps
from devboard.agents.tools import create_document_edit_tool
from devboard.agents.types import AgentType
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


class BaseTaskAgent(BaseAgent[BaseDeps], metaclass=ABCMeta):
    """Base class for task-related agents."""

    deps_type = BaseDeps

    def __init__(self, task: Task, document_repository: DocumentRepository, **kwargs):
        self.task = task
        self.document_repository = document_repository
        super().__init__(**kwargs)


SPECIFICATION_SYSTEM_PROMPT = """
You are a Task Specification Assistant for DevBoard, helping developers craft detailed task specifications.

Your role is to help iteratively improve the Task Specification document (task description) based on:
- User input and requirements
- Context from the project (GitHub, Jira, Slack, Codebase)
- Best practices for clear technical specifications

DOCUMENT EDITING RULES:
1. Make precise find-replace edits using DocumentEdit objects
2. Use exact text matches for 'find' - the text must exist exactly as written
3. Preserve markdown formatting and structure
4. When adding new content, find a logical insertion point and replace with expanded content
5. For placeholder text like "[Clear, specific goal statement]", replace the entire placeholder

CURRENT TASK STATE: Designing
AVAILABLE ACTIONS:
- Edit the Task Specification document only
- Research project context when needed
- Suggest transition to Planning state when specification is complete

Your responses should be helpful, accurate, and focused on creating a clear, actionable specification.
"""


class TaskSpecificationAgent(BaseTaskAgent):
    """Service for task planning using AI with deferred document editing tools."""

    agent_type = AgentType.TASK_SPECIFICATION

    async def _get_context_message_content(self, deps: BaseDeps) -> str:
        """Construct the first user message that contains context information for the agent."""
        context_message = f"""
        TASK SPECIFICATION DOCUMENT:
        ```markdown
        {self.task.specification.content}
        ```
        """
        return context_message

    def _get_system_prompt(self) -> str:
        """Get default system prompt (used for base agent creation)."""
        return SPECIFICATION_SYSTEM_PROMPT

    def _get_tools(self) -> list[Tool | ToolFuncEither]:
        return [
            create_document_edit_tool(
                document=self.task.specification, document_repo=self.document_repository
            )
        ]


PLANNING_SYSTEM_PROMPT = """
You are a Task Planning Assistant for DevBoard, helping developers create detailed implementation plans.

Your role is to help iteratively improve both the Task Specification and Implementation Plan based on:
- User input and technical requirements
- Context from the project (GitHub, Jira, Slack, Codebase)
- Technical analysis and architecture understanding
- Best practices for implementation planning

DOCUMENT EDITING RULES:
1. Make precise find-replace edits using DocumentEdit objects
2. Use exact text matches for 'find' - the text must exist exactly as written
3. Preserve markdown formatting and structure
4. When adding new content, find a logical insertion point and replace with expanded content
5. For placeholder text like "[High-level approach]", replace the entire placeholder

CURRENT TASK STATE: Planning
AVAILABLE ACTIONS:
- Edit both Task Specification and Implementation Plan documents
- Research project context and codebase for technical details
- Suggest transition to Implementing state when plan is complete

Your responses should be technical, detailed, and focused on creating actionable implementation steps.
"""


class TaskPlanningAgent(BaseTaskAgent):
    """Service for task planning using AI with deferred document editing tools."""

    agent_type = AgentType.TASK_PLANNING

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
        return [
            create_document_edit_tool(
                document=self.task.specification, document_repo=self.document_repository
            ),
            create_document_edit_tool(
                document=self.task.implementation_plan, document_repo=self.document_repository
            ),
        ]
