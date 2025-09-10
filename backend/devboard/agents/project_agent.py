"""Project Q&A Agent using PydanticAI for intelligent context-aware responses."""

import logging

import logfire
from pydantic_ai import Tool
from pydantic_ai.tools import ToolFuncEither

from devboard.agents.base_agent import BaseAgent
from devboard.agents.deps import BaseDeps
from devboard.agents.tools import get_relevant_context
from devboard.agents.types import AgentType
from devboard.services.context_assembly import (
    EagerContextData,
    OnDemandResourceInfo,
    ProjectContextData,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a Project Q&A Assistant for DevBoard, an AI-powered developer command center.

You help developers by answering questions about their projects using context from multiple sources:
- GitHub (PRs, issues, commits, repositories)
- Jira (tickets, projects, comments)
- Slack (messages, channels, conversations)
- Codebase (files, directories, code analysis)

IMPORTANT: You have access to EAGER context (pre-loaded small resources) and ON_DEMAND resources (descriptions only).
When you need specific information from an ON_DEMAND resource, use the get_relevant_context tool.

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


class ProjectAgent(BaseAgent):
    """Service for project Q&A using AI with context assembly."""
    agent_type = AgentType.PROJECT

    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return SYSTEM_PROMPT

    def _get_tools(self) -> list[Tool | ToolFuncEither]:
        return [get_relevant_context]

    async def chat(self, project_id: int, user_query: str, message_history: list = None) -> str:
        """Process a user query with project context.

        Args:
            project_id: The project ID for context gathering
            user_query: The user's question or query
            message_history: Previous conversation messages

        Returns:
            AI-generated response based on project context
        """
        with logfire.span("qa_agent.chat", project_id=project_id, query_length=len(user_query)):
            try:
                # Assemble project context
                with logfire.span("qa_agent.context_assembly"):
                    context_data = await self.context_service.get_project_context(
                        project_id, user_query
                    )

                # Create agent context
                project_context = ProjectDeps(
                    project_id=project_id,
                    eager_context=context_data.eager_context,
                    on_demand_resources=context_data.on_demand_resources,
                )

                # Log context stats
                logfire.info(
                    "Context assembled",
                    eager_resources=len(context_data.eager_context),
                    on_demand_resources=len(context_data.on_demand_resources),
                    provider_errors=len(context_data.provider_errors),
                )

                # Prepare initial context summary for the agent
                context_summary = self._build_context_summary(context_data)

                # Combine user query with context information
                enhanced_prompt = f"""
USER QUERY: {user_query}

AVAILABLE CONTEXT:
{context_summary}

Please answer the user's query using the available context. If you need more specific information from any ON_DEMAND resource, use the get_relevant_context tool.
"""

                # Use message history if provided
                if message_history is None:
                    message_history = []

                # Run the agent using base class method
                result, _ = await self.process_message_with_history(
                    enhanced_prompt, message_history, project_context
                )

                # Since QA agent doesn't use deferred tools, we just return the text response
                logfire.info("QA agent response generated", response_length=len(result.data))
                return result.data
            except Exception as e:
                logfire.error(
                    "Error processing chat query", project_id=project_id, error=str(e), exc_info=e
                )
                return f"I encountered an error processing your query: {e}. Please try again or contact support if the issue persists."

    def _build_context_summary(self, context_data: ProjectContextData) -> str:
        """Build a summary of available context for the agent."""
        summary_parts: list[str] = []

        # EAGER context summary
        if context_data.eager_context:
            summary_parts.append("EAGER CONTEXT (pre-loaded):")
            for context in context_data.eager_context:
                description = context.description or "No description"
                summary_parts.append(
                    f"- [{context.provider_type.upper()}] {context.uri}: {description}"
                )

        # ON_DEMAND resources summary
        if context_data.on_demand_resources:
            summary_parts.append("\nON_DEMAND RESOURCES (use get_relevant_context tool):")
            for resource in context_data.on_demand_resources:
                summary_parts.append(
                    f"- [{resource.provider_type.upper()}] {resource.uri}: {resource.description}"
                )

        if not summary_parts:
            return "No context resources configured for this project."

        return "\n".join(summary_parts)


# Global Q&A agent service instance
qa_agent_service = ProjectAgent()

