"""Base agent service with shared functionality for PydanticAI message handling."""

import datetime
from collections.abc import AsyncIterator, Generator

import logfire
from pydantic_ai import Agent, AgentRunResultEvent, AgentStreamEvent, FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.messages import (
    FinalResultEvent,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult
from pydantic_ai.tools import (
    DeferredToolApprovalResult,
    DeferredToolRequests,
    DeferredToolResults,
    ToolApproved,
    ToolDenied,
)

from devboard.agents.base_agent import BaseAgent
from devboard.agents.engines.internal.utils import convert_tool_args
from devboard.agents.events import (
    ConversationEvent,
    MessageRole,
    TextMessage,
    ToolCall,
    ToolCallRequest,
    ToolResult,
)
from devboard.agents.language_models import LanguageModel
from devboard.agents.roles.base import AgentRole
from devboard.api.schemas.agent_conversation import (
    ToolApprovals,
)
from devboard.services.context_assembly import ProjectContextData


class InternalAgent(BaseAgent):
    """PydanticAI-based agent that delegates behavior to a Role.

    This agent uses a Role instance to define its system prompt, tools, and context,
    making the agent behavior completely determined by the role configuration.
    """

    def __init__(
        self,
        role: AgentRole,
        model: LanguageModel,
        conversation_history: list[ModelMessage] | None = None,
    ):
        """Initialize internal agent with role.

        Args:
            role: Role defining agent behavior (prompts, tools, context)
            model: Language model to use
            conversation_history: Previous conversation messages
        """
        super().__init__(role, model)
        self.conversation_history = conversation_history or []
        self.last_run_result: AgentRunResult | None = None

    def _create_agent(self) -> Agent:
        """Create PydanticAI agent using role's configuration."""
        agent = Agent(
            self._get_model(),
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

    async def build_system_and_context_messages(self) -> ModelRequest:
        """Build initial system and context messages from role.

        Returns:
            Model request with system prompt and context message
        """
        context_content = await self.role.get_context_content()
        parts: list[ModelRequestPart] = [
            SystemPromptPart(content=self.role.get_system_prompt()),
            UserPromptPart(content="CURRENT STATE AND CONTEXT:\n" + context_content),
        ]

        return ModelRequest(parts=parts)

    def _convert_tool_approvals_to_deferred_results(self, approvals: ToolApprovals) -> DeferredToolResults:
        """Convert ToolApprovals model to PydanticAI DeferredToolResults.

        Args:
            approvals: ToolApprovals model with approval decisions

        Returns:
            DeferredToolResults for PydanticAI agent execution
        """
        converted_approvals: dict[str, DeferredToolApprovalResult] = {}
        for tool_call_id, decision in approvals.approvals.items():
            if decision.approved:
                converted_approvals[tool_call_id] = ToolApproved()
            else:
                if decision.feedback:
                    message = f"Tool call DENIED with feedback: {decision.feedback}"
                else:
                    message = "The tool call was DENIED."
                converted_approvals[tool_call_id] = ToolDenied(message=message)

        return DeferredToolResults(approvals=converted_approvals)

    def _convert_pydantic_event_to_conversation_events(self, event: AgentStreamEvent) -> Generator[ConversationEvent]:
        """Convert PydanticAI stream event to ConversationEvent.

        Args:
            event: PydanticAI stream event

        Returns:
            ConversationEvent or None if event should not be included
        """

        # Ignore partial streaming event types for now
        if isinstance(event, (PartStartEvent, PartDeltaEvent, PartEndEvent, FinalResultEvent)):
            return

        logfire.info(f"Handling PydanticAI stream event: {repr(event)}")

        timestamp = datetime.datetime.now(datetime.UTC)

        if isinstance(event, FunctionToolCallEvent):
            # Extract tool call information
            part = event.part
            yield ToolCall(
                tool_call_id=part.tool_call_id,
                tool_name=part.tool_name,
                tool_args=convert_tool_args(part.args),
                timestamp=timestamp,
            )

        elif isinstance(event, FunctionToolResultEvent):
            # Extract tool result information
            result_part = event.result
            yield ToolResult(
                tool_call_id=result_part.tool_call_id,
                result_content=str(result_part.content),
                is_error=isinstance(result_part, RetryPromptPart),
                timestamp=timestamp,
            )
        elif isinstance(event, AgentRunResultEvent):
            result = event.result
            self.last_run_result = result
            # Update conversation history with new messages
            self.conversation_history.extend(result.new_messages())
            # Extract final result information
            if isinstance(result.output, DeferredToolRequests):
                # Convert deferred tool requests to ToolCallRequest events
                for tool_call in result.output.approvals:
                    yield ToolCallRequest(
                        tool_call_id=tool_call.tool_call_id,
                        tool_name=tool_call.tool_name,
                        tool_args=tool_call.args if tool_call.args else None,
                        timestamp=timestamp,
                    )
            elif isinstance(result.output, str):
                # Text response
                yield TextMessage(
                    role=MessageRole.AGENT,
                    text_content=result.output,
                    timestamp=timestamp,
                )
            else:
                raise ValueError(f"Unexpected agent result output: {result.output}")

        return

    async def stream_events(
        self,
        prompt_or_approvals: str | ToolApprovals,
    ) -> AsyncIterator[ConversationEvent]:
        """Stream conversation events from agent execution.

        Args:
            prompt_or_approvals: The user's message or tool approval model

        Yields:
            Conversation events as they are generated during agent execution
        """
        # Build system prompt and context message dynamically each time
        initial_request = await self.build_system_and_context_messages()
        dummy_response = ModelResponse(
            parts=[TextPart(content="Understood, I will use the provided context and tools to answer your query.")]
        )
        total_message_history: list[ModelMessage] = [
            initial_request,
            dummy_response,
        ] + self.conversation_history

        agent = self._create_agent()

        # Stream events from the agent
        if isinstance(prompt_or_approvals, ToolApprovals):
            deferred_results = self._convert_tool_approvals_to_deferred_results(prompt_or_approvals)
            event_iterator = agent.run_stream_events(
                deferred_tool_results=deferred_results,
                message_history=total_message_history,
            )
        else:
            event_iterator = agent.run_stream_events(
                user_prompt=prompt_or_approvals,
                message_history=total_message_history,
            )

        async for pydantic_event in event_iterator:
            # Convert and yield event
            for conv_event in self._convert_pydantic_event_to_conversation_events(pydantic_event):
                yield conv_event

        # Add final result event
        if self.last_run_result is None:
            raise ValueError("Agent execution did not produce a result")

    def get_new_messages(self) -> list[ModelMessage]:
        """Get new messages from the last agent run.

        Can be called multiple times - does not clear buffer.

        Returns:
            List of new messages from the last run
        """
        if not self.last_run_result:
            return []
        return self.last_run_result.new_messages()

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
