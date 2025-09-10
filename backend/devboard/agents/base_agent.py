"""Base agent service with shared functionality for PydanticAI message handling."""

import logging
from abc import abstractmethod
from typing import Any, Generic, TypeVar

from pydantic_ai import Agent, Tool
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.tools import DeferredToolRequests, ToolFuncEither

from devboard.agents.deps import BaseDeps
from devboard.agents.llm_service import llm_service
from devboard.agents.types import AgentType
from devboard.services.context_assembly import ContextAssemblyService, ProjectContextData, context_assembly_service

logger = logging.getLogger(__name__)

TDeps = TypeVar("TDeps", bound=BaseDeps)

class BaseAgent(Generic[TDeps]):
    """Base class for all document-editing agents using PydanticAI."""
    agent_type: AgentType
    deps_type: type[TDeps] = BaseDeps

    def __init__(
        self, context_service: ContextAssemblyService | None = None
    ):
        self.context_service = context_service or context_assembly_service
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent[TDeps]:
        """Create the PydanticAI agent with context tools."""

        preferred_model = self._get_preferred_model()

        agent = Agent[TDeps](
            preferred_model,
            deps_type=self.deps_type,
            system_prompt=self._get_system_prompt(),
            tools=self._get_tools(),
        )

        return agent

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass

    def _get_tools(self) -> list[Tool | ToolFuncEither]:
        """Get the tools for this agent."""
        return []

    def _get_preferred_model(self) -> str:
        """Get preferred model for this agent type."""
        return llm_service.get_preferred_model_for_agent(self.agent_type)

    @abstractmethod
    async def get_context_message_content(self, deps: TDeps) -> str:
        """Construct the first user message that contains context information for the agent."""
        # TODO: Something like this
        # Build context summary
        context_data = await self.context_service.get_project_context(
            project_id, user_message
        )
        context_summary = self._build_context_summary(context_data)

        # Create prompt with document state and context
        documents_info = self._build_documents_info(current_description, current_plan, state)

        # Get document template if necesary
        template_service.get_template(TemplateType.IMPLEMENTATION_PLAN).replace(
            "[Title]", task_title
        )

        enhanced_prompt = f"""
        USER MESSAGE: {user_message}

        CURRENT DOCUMENTS:
        {documents_info}

        AVAILABLE CONTEXT:
        {context_summary}

        Please help with document editing using the available tools. You can:
        - Use get_relevant_context to research information
        - Use edit_task_specification to modify the task specification (always available)
        - Use edit_implementation_plan to modify the implementation plan (available in Planning state)

        EDITING GUIDELINES:
        - Make precise find-replace edits with exact text matching
        - Provide clear reasoning for your edits
        - Consider the current state ({state.value}) when choosing which documents to edit
        - Use context research to inform your edits when needed
        """

    async def build_system_and_context_messages(self, deps: TDeps) -> ModelRequest:
        """
        Build the initial system and context messages, which will be prepended to the conversation history.
        :param deps:
        :return:
        """
        parts: list[ModelRequestPart] = [SystemPromptPart(content=self._get_system_prompt())]

        context_msg_content = await self.get_context_message_content(deps)
        parts.append(UserPromptPart(content=context_msg_content))

        return ModelRequest(parts=parts)

    async def process_message_with_history(
        self, user_message: str, message_history: list[ModelMessage], deps: BaseDeps
    ) -> DeferredToolRequests | str:
        """Process a user message with conversation history.

        Args:
            user_message: The user's message
            message_history: Previous conversation messages
            deps: Agent-specific dependencies/context

        Returns:
            Final response message, or deferred tool requests if applicable
        """
        initial_request = await self.build_system_and_context_messages(deps)
        dummy_response = ModelResponse(parts=[TextPart(content="Understood, I will use the provided context and tools to answer your query.")])
        # Run the agent with message history
        result = await self.agent.run(
            user_message, deps=deps, message_history=[initial_request, dummy_response] + message_history
        )
        return result.output

    async def process_tool_approval(
        self,
        deferred_results: Any,  # DeferredToolResults type
        message_history: list,
        context: BaseDeps,
    ) -> Any:  # Returns ModelResponse
        """Continue agent execution after tool approval/denial.

        Args:
            deferred_results: Results of tool approval/denial
            message_history: Current conversation history
            context: Agent-specific context

        Returns:
            Final agent response after tool processing
        """

        result = await self.agent.run(
            deferred_results, deps=context, message_history=message_history
        )

        return result

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

