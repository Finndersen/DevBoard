"""Base agent service with shared functionality for PydanticAI message handling."""

import datetime
from collections.abc import AsyncIterator, Generator

import logfire
from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    Tool,
)
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
from devboard.agents.roles.base import AgentRole
from devboard.api.schemas.agent_conversation import (
    ToolApprovals,
)
from devboard.db.models.language_model import LanguageModelDB


class InternalAgent(BaseAgent):
    """PydanticAI-based agent that delegates behavior to a Role.

    This agent uses a Role instance to define its system prompt, tools, and context,
    making the agent behavior completely determined by the role configuration.
    """

    def __init__(
        self,
        role: AgentRole,
        model: LanguageModelDB,
        conversation_history: list[ModelMessage] | None = None,
        additional_tools: list[Tool] | None = None,
        custom_instructions: str | None = None,
    ):
        """Initialize internal agent with role.

        Args:
            role: Role defining agent behavior (prompts, tools, context)
            model: Language model to use
            conversation_history: Previous conversation messages
            additional_tools: Extra tools to add beyond those defined by the role
            custom_instructions: User-defined instructions to append to the base system prompt
        """
        super().__init__(role, model, additional_tools, custom_instructions)
        self.conversation_history = conversation_history or []
        self.last_run_result: AgentRunResult[str | DeferredToolRequests] | None = None

    def _create_agent(self) -> Agent[None, str | DeferredToolRequests]:
        """Create PydanticAI agent using role's configuration."""
        agent: Agent[None, str | DeferredToolRequests] = Agent(
            self._get_model(),
            system_prompt=self.get_full_system_prompt(),
            tools=self.get_tools(),
            output_type=DeferredToolRequests | str,
        )
        return agent

    def _get_model(self) -> str:
        """Get the model identifier for this agent instance.

        Returns the model ID with provider-specific adjustments for PydanticAI compatibility.
        """
        assert self.model is not None, "InternalAgent requires a non-None model"
        # Replace google with google-gla for compatibility with PydanticAI
        return self.model.model_id.replace("google", "google-gla")

    async def build_system_and_context_messages(self) -> ModelRequest:
        """Build initial system and context messages from role.

        Returns:
            Model request with system prompt and context message
        """
        context_content = await self.role.get_context_content()
        parts: list[ModelRequestPart] = [
            SystemPromptPart(content=self.get_full_system_prompt()),
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
        converted_approvals: dict[str, bool | DeferredToolApprovalResult] = {}
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

    def _convert_pydantic_event_to_conversation_events(
        self, event: AgentStreamEvent | AgentRunResultEvent[str | DeferredToolRequests]
    ) -> Generator[ConversationEvent]:
        """Convert PydanticAI stream event to ConversationEvent.

        Args:
            event: PydanticAI stream event or agent run result event

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
            # Extract model name from the last ModelResponse in new messages
            model_name: str | None = None
            for msg in reversed(result.new_messages()):
                if isinstance(msg, ModelResponse):
                    model_name = msg.model_name
                    break
            # Extract final result information
            if isinstance(result.output, DeferredToolRequests):
                # Convert deferred tool requests to ToolCallRequest events
                for tool_call in result.output.approvals:
                    yield ToolCallRequest(
                        tool_call_id=tool_call.tool_call_id,
                        tool_name=tool_call.tool_name,
                        tool_args=tool_call.args if tool_call.args else None,
                        timestamp=timestamp,
                        model=model_name,
                    )
            elif isinstance(result.output, str):  # pyright: ignore[reportUnnecessaryIsInstance]
                # Text response
                yield TextMessage(
                    role=MessageRole.AGENT,
                    text_content=result.output,
                    timestamp=timestamp,
                    model=model_name,
                )
            else:
                raise ValueError(f"Unexpected agent result output: {result.output}")

        return

    async def _build_message_history(self) -> list[ModelMessage]:
        """Build full message history including initial system/context messages."""
        initial_request = await self.build_system_and_context_messages()
        dummy_response = ModelResponse(
            parts=[TextPart(content="Understood, I will use the provided context and tools to answer your query.")]
        )
        return [initial_request, dummy_response] + self.conversation_history

    async def run(self, prompt: str) -> TextMessage:
        """Execute agent and return only the final text message without streaming intermediate events.

        For non-interactive use only. Still updates conversation_history and last_run_result
        so get_new_messages() works correctly.

        Args:
            prompt: The user prompt to send to the agent

        Returns:
            The final TextMessage from the agent
        """
        agent = self._create_agent()
        message_history = await self._build_message_history()
        result = await agent.run(user_prompt=prompt, message_history=message_history)

        self.last_run_result = result
        self.conversation_history.extend(result.new_messages())

        assert isinstance(result.output, str), (
            f"Expected text output for non-interactive run, got: {type(result.output)}"
        )
        return TextMessage(
            role=MessageRole.AGENT,
            text_content=result.output,
            timestamp=datetime.datetime.now(datetime.UTC),
        )

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
        agent = self._create_agent()
        message_history = await self._build_message_history()

        if isinstance(prompt_or_approvals, ToolApprovals):
            deferred_results = self._convert_tool_approvals_to_deferred_results(prompt_or_approvals)
            stream = agent.run_stream_events(deferred_tool_results=deferred_results, message_history=message_history)
        else:
            stream = agent.run_stream_events(user_prompt=prompt_or_approvals, message_history=message_history)

        async for pydantic_event in stream:
            for conv_event in self._convert_pydantic_event_to_conversation_events(pydantic_event):
                yield conv_event

        if self.last_run_result is None:
            raise ValueError("Agent execution did not produce a result")

    def get_new_messages(self) -> list[ModelMessage]:
        """Get new messages from the last agent run. Can be called multiple times."""
        if self.last_run_result is None:
            raise RuntimeError("get_new_messages() called before agent run completed")
        return self.last_run_result.new_messages()
