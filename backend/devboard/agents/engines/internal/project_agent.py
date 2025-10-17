"""Project Q&A Agent using PydanticAI for intelligent context-aware responses."""

from pydantic_ai import Tool
from pydantic_ai.tools import ToolFuncEither

from devboard.agents.engines.internal.base_agent import InternalAgent
from devboard.agents.engines.internal.deps import BaseDeps
from devboard.agents.engines.internal.tools import create_document_edit_tool
from devboard.agents.language_models import LanguageModel
from devboard.agents.roles.types import AgentRole
from devboard.db.models import Project
from devboard.db.repositories import DocumentRepository
from devboard.services.context_assembly import (
    EagerContextData,
    OnDemandResourceInfo,
)

SYSTEM_PROMPT = """
You are a Project Assistant for DevBoard, an AI-powered developer command center.

Your role is to assist a developer working on a software project called: "{project_name}". This includes:
- Answering questions about the project based on project specification, tasks, and associated context resources
- Discussing project requirements and goals in order to create new tasks or update project specification

You will have access to the project specification document, which you are able to edit using the provided tool.

You will also have access to various context sources related to the project, and should use the available tools to query these context sources to obtain the information required to answer the user's questions, or complete tasks

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


class ProjectDeps(BaseDeps):
    """Context data structure for the Q&A agent."""

    project_id: int
    eager_context: list[EagerContextData]
    on_demand_resources: list[OnDemandResourceInfo]


class ProjectAgent(InternalAgent[BaseDeps]):
    """Agent for managing and answering queries about a Project."""

    deps_type = BaseDeps
    agent_role = AgentRole.PROJECT

    def __init__(
        self,
        project: Project,
        document_repository: DocumentRepository,
        context_service,
        model: LanguageModel,
    ):
        self.project = project
        self.document_repository = document_repository
        super().__init__(
            context_service=context_service,
            model=model,
        )

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
        # LIVE DOCUMENTS

        These documents are available for editing and represent the current live state of the document (may be dynamically updated during the conversation).

        ## PROJECT SPECIFICATION DOCUMENT:
        ```markdown
        {self.project.specification.content}
        ```
        """
        return context_message
