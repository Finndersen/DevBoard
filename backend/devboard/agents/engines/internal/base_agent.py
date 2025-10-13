"""Base agent service with shared functionality for PydanticAI message handling."""

import logging
from abc import ABCMeta, abstractmethod

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
from pydantic_ai.run import AgentRunResult
from pydantic_ai.tools import (
    DeferredToolRequests,
    DeferredToolResults,
    ToolFuncEither,
)

from devboard.agents.engines.internal.deps import BaseDeps
from devboard.agents.roles.types import AgentRole
from devboard.services.context_assembly import (
    ContextAssemblyService,
    ProjectContextData,
)

logger = logging.getLogger(__name__)


class InternalAgent[TDeps: BaseDeps](metaclass=ABCMeta):
    """Base class for all internal agent definitions using PydanticAI."""

    agent_role: AgentRole
    deps_type: type[TDeps]

    def __init__(
        self,
        context_service: ContextAssemblyService,
        model_name: str,
    ):
        self.context_service = context_service
        self.model_name = model_name

    def _create_agent(self) -> Agent[TDeps]:
        """Create the PydanticAI agent with context tools."""

        agent = Agent[TDeps](
            self._get_model(),
            deps_type=self.deps_type,
            system_prompt=self._get_system_prompt(),
            tools=self._get_tools(),
            output_type=DeferredToolRequests | str,
        )

        return agent

    def _get_model(self) -> str:
        """Get the model name for this agent instance."""
        # Replace google with google-gla for compatibility with PydanticAI
        return self.model_name.replace("google", "google-gla")

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass

    @abstractmethod
    def _get_tools(self) -> list[Tool | ToolFuncEither]:
        """Get the tools for this agent."""
        pass

    @abstractmethod
    async def _get_context_message_content(self, deps: TDeps) -> str:
        """Construct the first user message that contains context information for the agent."""
        pass

    async def build_system_and_context_messages(self, deps: TDeps) -> ModelRequest:
        """
        Build the initial system and context messages, which will be prepended to the conversation history.
        :param deps:
        :return:
        """
        parts: list[ModelRequestPart] = [SystemPromptPart(content=self._get_system_prompt())]

        context_msg_content = await self._get_context_message_content(deps)
        parts.append(UserPromptPart(content=context_msg_content))

        return ModelRequest(parts=parts)

    async def run(
        self,
        prompt_or_approvals: str | DeferredToolResults,
        conversation_history: list[ModelMessage],
        deps: TDeps,
    ) -> AgentRunResult:
        """Process a user message with conversation history.

        Args:
            prompt_or_approvals: The user's message
            conversation_history: Previous conversation messages
            deps: Agent-specific dependencies/context

        Returns:
            Final response message, or deferred tool requests if applicable
        """
        # Build system prompt and context message dynamically each time
        initial_request = await self.build_system_and_context_messages(deps)
        dummy_response = ModelResponse(
            parts=[TextPart(content="Understood, I will use the provided context and tools to answer your query.")]
        )
        total_message_history: list[ModelMessage] = [
            initial_request,
            dummy_response,
        ] + conversation_history

        agent = self._create_agent()

        # Run the agent with message history
        if isinstance(prompt_or_approvals, DeferredToolResults):
            result = await agent.run(
                deferred_tool_results=prompt_or_approvals,
                deps=deps,
                message_history=total_message_history,
            )
        else:
            result = await agent.run(
                user_prompt=prompt_or_approvals,
                deps=deps,
                message_history=total_message_history,
            )

        return result

    def _build_context_summary(self, context_data: ProjectContextData) -> str:
        """
        Build a summary of available context for the agent.
        TODO: Rework
        """
        summary_parts: list[str] = []

        # EAGER context summary
        if context_data.eager_context:
            summary_parts.append("EAGER CONTEXT (pre-loaded):")
            for context in context_data.eager_context:
                description = context.description or "No description"
                summary_parts.append(f"- [{context.provider_type.upper()}] {context.uri}: {description}")

        # ON_DEMAND resources summary
        if context_data.on_demand_resources:
            summary_parts.append("\nON_DEMAND RESOURCES (use get_relevant_context tool):")
            for resource in context_data.on_demand_resources:
                summary_parts.append(f"- [{resource.provider_type.upper()}] {resource.uri}: {resource.description}")

        if not summary_parts:
            return "No context resources configured for this project."

        return "\n".join(summary_parts)
