"""Project Q&A Agent using PydanticAI for intelligent context-aware responses."""

import logging

from pydantic_ai import Tool
from pydantic_ai.tools import ToolFuncEither

from devboard.agents.base_agent import BaseAgent
from devboard.agents.deps import BaseDeps
from devboard.agents.tools import create_document_edit_tool
from devboard.agents.types import AgentType
from devboard.db.models import Project
from devboard.db.repositories import DocumentRepository
from devboard.services.context_assembly import (
    EagerContextData,
    OnDemandResourceInfo,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a Project Assistant for DevBoard, an AI-powered developer command center.

Your role is to assist a developer working on a software project called: "{project_name}".

You will have access to the project specification document, which you are able to edit using the provided tool.

You will also have access to various context sources related to the project, and should use the available tools to query these context sources to obtain the information required to answer the user's questions, or complete tasks

EDITING GUIDELINES:
- Make precise find-replace edits with exact text matching
- Provide clear reasoning for your edits
- Use context research to inform your edits when needed

Your responses should be:
- Accurate and based on the provided context
- Helpful for developers working on the project
- Clear and actionable when possible
- Honest about limitations if context is insufficient

Focus on connecting information across different sources to provide comprehensive insights.
"""


class ProjectDeps(BaseDeps):
    """Context data structure for the Q&A agent."""

    project_id: int
    eager_context: list[EagerContextData]
    on_demand_resources: list[OnDemandResourceInfo]


class ProjectAgent(BaseAgent[BaseDeps]):
    """Agent for managing and answering queries about a Project."""

    deps_type = BaseDeps
    agent_type = AgentType.PROJECT

    def __init__(self, project: Project, document_repository: DocumentRepository, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.document_repository = document_repository

    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return SYSTEM_PROMPT.format(project_name=self.project.name)

    def _get_tools(self) -> list[Tool | ToolFuncEither]:
        return [create_document_edit_tool(self.project.specification, self.document_repository)]

    async def _get_context_message_content(self, deps: BaseDeps) -> str:
        """Construct the first user message that contains context information for the agent."""
        # TODO: Something like this
        # Build context summary
        # context_data = await self.context_service.get_project_context(
        #     project_id, user_message
        # )
        # context_summary = self._build_context_summary(context_data)

        # Get document template if necesary
        # template_service.get_template(TemplateType.IMPLEMENTATION_PLAN).replace(
        #     "[Title]", task_title
        # )

        context_message = f"""
        PROJECT SPECIFICATION DOCUMENT:
        ```markdown
        {self.project.specification.content}
        ```
        """
        return context_message
