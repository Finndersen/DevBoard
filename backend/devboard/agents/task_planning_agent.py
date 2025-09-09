"""Task Planning Agent using PydanticAI for interactive document crafting."""

import logging
from enum import Enum

import logfire
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from devboard.agents.llm_service import AgentType, llm_service
from devboard.services.context_assembly import (
    ContextAssemblyService,
    EagerContextData,
    OnDemandResourceInfo,
    ProjectContextData,
)
from devboard.services.template_service import TemplateType, template_service

logger = logging.getLogger(__name__)


class TaskState(str, Enum):
    """Task states that support document crafting."""

    DESIGNING = "Designing"
    PLANNING = "Planning"


class DocumentType(str, Enum):
    """Document types that can be edited."""

    SPECIFICATION = "specification"
    IMPLEMENTATION_PLAN = "implementation_plan"


class DocumentEdit(BaseModel):
    """A single find-replace edit operation on a document."""

    find: str = Field(..., description="Exact text to find in the document")
    replace: str = Field(..., description="Text to replace the found text with")


class TaskPlanningResponse(BaseModel):
    """Structured response from the task planning agent."""

    message: str = Field(..., description="Natural language response to user")
    task_specification_edits: list[DocumentEdit] | None = Field(
        None, description="Edits for task specification document"
    )
    task_implementation_plan_edits: list[DocumentEdit] | None = Field(
        None, description="Edits for implementation plan document"
    )


class TaskContext(BaseModel):
    """Context data structure for the task planning agent."""

    task_id: int
    task_title: str
    task_description: str | None
    task_implementation_plan: str | None
    task_state: TaskState
    project_id: int
    eager_context: list[EagerContextData]
    on_demand_resources: list[OnDemandResourceInfo]


SYSTEM_PROMPTS = {
    TaskState.DESIGNING: """
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
""",
    TaskState.PLANNING: """
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
""",
}


class TaskPlanningAgentService:
    """Service for task planning using AI with document crafting capabilities."""

    def __init__(self, context_service: ContextAssemblyService | None = None):
        self.context_service = context_service or ContextAssemblyService()
        self.agents = self._create_agents()

    def _create_agents(self) -> dict[TaskState, Agent[TaskContext, TaskPlanningResponse]]:
        """Create state-specific PydanticAI agents."""
        agents = {}

        # Get preferred model for planning agents
        preferred_model = llm_service.get_preferred_model_for_agent(AgentType.PLANNING)

        for state in TaskState:
            agent = Agent(
                preferred_model,
                deps_type=TaskContext,
                output_type=TaskPlanningResponse,
                system_prompt=SYSTEM_PROMPTS[state],
            )

            @agent.tool
            async def get_relevant_context(
                ctx: RunContext[TaskContext], resource_uri: str, query: str
            ) -> str:
                """Research specific information from project context.

                Args:
                    resource_uri: URI of the resource to query (from on_demand_resources)
                    query: Specific question about the resource

                Returns:
                    Focused context relevant to your query
                """
                with logfire.span(
                    "task_agent.get_relevant_context",
                    resource_uri=resource_uri,
                    query_length=len(query),
                ):
                    try:
                        available_uris = [res.uri for res in ctx.deps.on_demand_resources]
                        if resource_uri not in available_uris:
                            logfire.warn("Resource not available", resource_uri=resource_uri)
                            return f"Error: Resource {resource_uri} not available"

                        result = await self.context_service.get_on_demand_context(
                            resource_uri, query
                        )
                        logfire.info("Context retrieved", result_length=len(result))
                        return result
                    except Exception as e:
                        logfire.error("Error getting context", error=str(e), exc_info=e)
                        return f"Error retrieving context: {e}"

            agents[state] = agent

        return agents

    async def process_message(
        self,
        task_id: int,
        task_title: str,
        task_description: str | None,
        task_implementation_plan: str | None,
        task_state: str,
        project_id: int,
        user_message: str,
    ) -> TaskPlanningResponse:
        """Process a user message and return structured response with document edits."""

        state = TaskState(task_state)

        with logfire.span(
            "task_planning_agent.process_message", task_id=task_id, task_state=task_state
        ):
            try:
                # Assemble project context
                with logfire.span("task_agent.context_assembly"):
                    context_data = await self.context_service.get_project_context(
                        project_id, user_message
                    )

                # Initialize documents with templates if empty
                current_description = task_description
                current_plan = task_implementation_plan

                if not current_description and state == TaskState.DESIGNING:
                    current_description = template_service.get_template(
                        TemplateType.TASK_SPECIFICATION
                    ).replace("[Title]", task_title)

                if not current_plan and state == TaskState.PLANNING:
                    current_plan = template_service.get_template(
                        TemplateType.IMPLEMENTATION_PLAN
                    ).replace("[Title]", task_title)

                # Create agent context
                task_context = TaskContext(
                    task_id=task_id,
                    task_title=task_title,
                    task_description=current_description,
                    task_implementation_plan=current_plan,
                    task_state=state,
                    project_id=project_id,
                    eager_context=context_data.eager_context,
                    on_demand_resources=context_data.on_demand_resources,
                )

                # Build context summary
                context_summary = self._build_context_summary(context_data)

                # Create prompt with document state and context
                documents_info = self._build_documents_info(
                    current_description, current_plan, state
                )

                enhanced_prompt = f"""
USER MESSAGE: {user_message}

CURRENT DOCUMENTS:
{documents_info}

AVAILABLE CONTEXT:
{context_summary}

Please respond with appropriate document edits and a helpful message. If you need more specific information, use the get_relevant_context tool to research.

EDITING GUIDELINES:
- Make precise find-replace edits
- Use exact text for 'find' parameter
- Include rationale for significant changes
- Preserve document structure and formatting
- Only edit documents appropriate for current state ({state.value})
"""

                # Run the appropriate agent
                agent = self.agents[state]
                preferred_model = llm_service.get_preferred_model_for_agent(AgentType.PLANNING)
                with logfire.span("task_agent.ai_inference", model=preferred_model):
                    result = await agent.run(enhanced_prompt, deps=task_context)

                logfire.info(
                    "Task planning response generated",
                    response_length=len(result.output.message),
                    spec_edit_count=len(result.output.task_specification_edits)
                    if result.output.task_specification_edits
                    else 0,
                    plan_edit_count=len(result.output.task_implementation_plan_edits)
                    if result.output.task_implementation_plan_edits
                    else 0,
                )

                return result.output

            except Exception as e:
                logfire.error("Error processing message", task_id=task_id, error=str(e), exc_info=e)
                return TaskPlanningResponse(
                    message=f"I encountered an error processing your message: {e}. Please try again."
                )

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

    def _build_documents_info(
        self, description: str | None, implementation_plan: str | None, state: TaskState
    ) -> str:
        """Build information about current document state."""
        info_parts: list[str] = []

        if state == TaskState.DESIGNING:
            info_parts.append("TASK SPECIFICATION (editable):")
            if description:
                preview = description[:200] + "..." if len(description) > 200 else description
                info_parts.append(f"Current content preview: {preview}")
            else:
                info_parts.append("No content yet - will be initialized with template")

        elif state == TaskState.PLANNING:
            info_parts.append("TASK SPECIFICATION (editable):")
            if description:
                preview = description[:150] + "..." if len(description) > 150 else description
                info_parts.append(f"Content preview: {preview}")
            else:
                info_parts.append("Empty - will be initialized with template")

            info_parts.append("\nIMPLEMENTATION PLAN (editable):")
            if implementation_plan:
                preview = (
                    implementation_plan[:150] + "..."
                    if len(implementation_plan) > 150
                    else implementation_plan
                )
                info_parts.append(f"Content preview: {preview}")
            else:
                info_parts.append("Empty - will be initialized with template")

        return "\n".join(info_parts)


# Global task planning agent service instance
task_planning_agent_service = TaskPlanningAgentService()
