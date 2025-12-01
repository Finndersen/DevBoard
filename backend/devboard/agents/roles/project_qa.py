"""Project Q&A role for answering questions and managing project specifications."""

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.base import AgentRole
from devboard.agents.tools import create_document_edit_tool, create_set_document_content_tool
from devboard.agents.tools.sub_agent_tools import CodebaseInvestigationContext, create_multi_codebase_investigation_tool
from devboard.db.models import Project
from devboard.db.repositories import DocumentRepository

PROJECT_QA_ROLE_PROMPT = """
You are a Project Assistant for DevBoard, an AI-powered developer command center.

Your role is to assist a developer working on a software project. This includes:
- Answering questions about the project based on project specification, tasks, and associated context resources
- Discussing project requirements and goals in order to create new tasks or update project specification

You will have access to the project specification document, which you are able to edit using the provided tools.

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


def build_project_qa_context(project: Project) -> str:
    """Build context for project Q&A agent.

    Includes project metadata and specification document.

    Note: Requires project to be loaded within an active SQLAlchemy session,
    as it will lazy-load relationships if needed.

    Args:
        project: Project instance with eager-loaded documents

    Returns:
        Formatted context string
    """
    context = f"""
PROJECT NAME: {project.name}

PROJECT SPECIFICATION DOCUMENT:
```markdown
{project.specification.content or "<EMPTY>"}
```
"""
    return context


class ProjectQAAgentRole(AgentRole):
    """Role for project Q&A and specification management."""

    def __init__(
        self,
        project: Project,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
    ):
        """Initialize project Q&A role.

        Args:
            project: Project instance
            document_repository: Repository for document operations
            agent_config_service: Service for agent configuration
        """
        self.project = project
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service

    def get_system_prompt(self) -> str:
        """Get the system prompt for project Q&A role."""
        return PROJECT_QA_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for project Q&A role.

        Returns:
            List of document editing tools and codebase investigation tool
        """
        tools = [
            create_set_document_content_tool(self.project.specification, self.document_repository),
            create_document_edit_tool(self.project.specification, self.document_repository),
        ]

        # Add codebase investigation tool if project has codebases
        if self.project.codebases:
            tools.append(
                create_multi_codebase_investigation_tool(
                    [
                        CodebaseInvestigationContext(codebase=cb, working_dir=cb.local_path)
                        for cb in self.project.codebases
                    ],
                    self.agent_config_service,
                )
            )

        return tools

    async def get_context_content(self) -> str:
        """Get context content for project Q&A role.

        Returns:
            Formatted context containing project details and specification
        """
        return build_project_qa_context(self.project)
