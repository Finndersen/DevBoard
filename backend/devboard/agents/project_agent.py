"""Project Q&A Agent using PydanticAI for intelligent context-aware responses."""

import logging

import logfire
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from devboard.services.context_assembly import (
    ContextAssemblyService,
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


class ProjectContext(BaseModel):
    """Context data structure for the Q&A agent."""

    project_id: int
    eager_context: list[EagerContextData]
    on_demand_resources: list[OnDemandResourceInfo]


class QAAgentService:
    """Service for project Q&A using AI with context assembly."""

    def __init__(self, context_service: ContextAssemblyService | None = None):
        self.context_service = context_service or ContextAssemblyService()
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent[ProjectContext]:
        """Create the PydanticAI agent with context tools."""

        agent = Agent(
            "openai:gpt-4o-mini",  # Using OpenAI as default, can be configured
            deps_type=ProjectContext,
            system_prompt=SYSTEM_PROMPT,
        )

        @agent.tool
        async def get_relevant_context(
            ctx: RunContext[ProjectContext], resource_uri: str, query: str
        ) -> str:
            """Get focused context from an ON_DEMAND resource.

            Use this tool when you need specific information from a resource that's
            only available as a description in the on_demand_resources list.

            Args:
                resource_uri: The URI of the resource to query (must be from on_demand_resources)
                query: Specific question about the resource

            Returns:
                Focused context relevant to your query
            """
            with logfire.span(
                "qa_agent.get_relevant_context", resource_uri=resource_uri, query_length=len(query)
            ):
                try:
                    # Verify the resource is available
                    available_uris = [res.uri for res in ctx.deps.on_demand_resources]
                    if resource_uri not in available_uris:
                        logfire.warn(
                            "Resource not available",
                            resource_uri=resource_uri,
                            available_count=len(available_uris),
                        )
                        return f"Error: Resource {resource_uri} not available for this project"

                    result = await self.context_service.get_on_demand_context(resource_uri, query)
                    logfire.info("On-demand context retrieved", result_length=len(result))
                    return result
                except Exception as e:
                    logfire.error(
                        "Error getting on-demand context",
                        resource_uri=resource_uri,
                        error=str(e),
                        exc_info=e,
                    )
                    return f"Error retrieving context: {e}"

        return agent

    async def chat(self, project_id: int, user_query: str) -> str:
        """Process a user query with project context.

        Args:
            project_id: The project ID for context gathering
            user_query: The user's question or query

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
                project_context = ProjectContext(
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

                # Run the agent
                with logfire.span("qa_agent.ai_inference", model="openai:gpt-4o-mini"):
                    result = await self.agent.run(enhanced_prompt, deps=project_context)

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
qa_agent_service = QAAgentService()
