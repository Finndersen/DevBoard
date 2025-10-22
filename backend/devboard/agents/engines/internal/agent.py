"""Base agent service with shared functionality for PydanticAI message handling."""

from collections.abc import AsyncIterator

from pydantic_ai import Agent, AgentRunResultEvent, AgentStreamEvent
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
)

from devboard.agents.engines.internal.deps import BaseDeps
from devboard.agents.language_models import LanguageModel
from devboard.agents.roles.base import Role
from devboard.services.context_assembly import ProjectContextData


class InternalAgent[TDeps: BaseDeps]:
    """PydanticAI-based agent that delegates behavior to a Role.

    This agent uses a Role instance to define its system prompt, tools, and context,
    making the agent behavior completely determined by the role configuration.
    """

    def __init__(
        self,
        role: Role,
        model: LanguageModel,
        deps_type: type[TDeps] = BaseDeps,
    ):
        """Initialize internal agent with role.

        Args:
            role: Role defining agent behavior (prompts, tools, context)
            model: Language model to use
            deps_type: Dependencies type for PydanticAI agent
        """
        self.role = role
        self.model = model
        self.deps_type = deps_type

    def _create_agent(self) -> Agent[TDeps]:
        """Create PydanticAI agent using role's configuration."""
        agent = Agent[TDeps](
            self._get_model(),
            deps_type=self.deps_type,
            system_prompt=self.role.get_system_prompt(),
            tools=self.role.get_tools(),
            output_type=DeferredToolRequests | str,
        )
        return agent

    def _get_model(self) -> str:
        """Get the model identifier for this agent instance.

        Returns the model ID with provider-specific adjustments for PydanticAI compatibility.
        """
        # Replace google with google-gla for compatibility with PydanticAI
        return self.model.id.replace("google", "google-gla")

    async def build_system_and_context_messages(self, deps: TDeps) -> ModelRequest:
        """Build initial system and context messages from role.

        Args:
            deps: Agent dependencies

        Returns:
            Model request with system prompt and context message
        """
        parts: list[ModelRequestPart] = [SystemPromptPart(content=self.role.get_system_prompt())]

        context_content = await self.role.get_context_content()
        parts.append(UserPromptPart(content="CURRENT STATE AND CONTEXT:\n" + context_content))

        return ModelRequest(parts=parts)

    async def stream_events(
        self,
        prompt_or_approvals: str | DeferredToolResults,
        conversation_history: list[ModelMessage],
        deps: TDeps,
    ) -> AsyncIterator[AgentStreamEvent]:
        """Stream events from agent execution.

        Args:
            prompt_or_approvals: The user's message or tool approval results
            conversation_history: Previous conversation messages
            deps: Agent-specific dependencies/context

        Yields:
            Stream events from PydanticAI agent execution
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

        # Stream events from the agent
        if isinstance(prompt_or_approvals, DeferredToolResults):
            async for event in agent.run_stream_events(
                deferred_tool_results=prompt_or_approvals,
                deps=deps,
                message_history=total_message_history,
            ):
                yield event
        else:
            async for event in agent.run_stream_events(
                user_prompt=prompt_or_approvals,
                deps=deps,
                message_history=total_message_history,
            ):
                yield event

    async def run(
        self,
        prompt_or_approvals: str | DeferredToolResults,
        conversation_history: list[ModelMessage],
        deps: TDeps,
    ) -> AgentRunResult:
        """Process a user message with conversation history.

        Args:
            prompt_or_approvals: The user's message or tool approval results
            conversation_history: Previous conversation messages
            deps: Agent-specific dependencies/context

        Returns:
            Final response message, or deferred tool requests if applicable
        """
        # Use stream_events and consume the iterator to get final result
        result = None
        async for event in self.stream_events(prompt_or_approvals, conversation_history, deps):
            if isinstance(event, AgentRunResultEvent):
                result = event.result

        if result is None:
            raise ValueError("Agent execution did not produce a result")

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
