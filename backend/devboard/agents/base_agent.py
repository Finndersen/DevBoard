"""Base agent interface for all agent implementations."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pydantic_ai import Tool

from devboard.agents.events import ConversationEvent
from devboard.agents.language_models import LanguageModel
from devboard.agents.roles.base import AgentRole
from devboard.api.schemas.agent_conversation import ToolApprovals

CUSTOM_INSTRUCTIONS_SEPARATOR = "\n\n## Additional Instructions\n\n"

SHARED_PROMPT_SUFFIX = (
    "\n\n## Error Handling\n\n"
    'If an MCP tool call fails with a "Stream closed" or "Tool execution was interrupted." error, '
    "stop immediately and report the error to the user — do not retry or continue. "
    "The user will need to resolve the issue and retry."
)


class BaseAgent(ABC):
    """Abstract base class for all agent implementations.

    Provides a unified interface for agent execution with consistent
    method signatures across different engine implementations.
    """

    def __init__(
        self,
        role: AgentRole,
        model: LanguageModel | None,
        additional_tools: list[Tool] | None = None,
        custom_instructions: str | None = None,
    ):
        """Initialize base agent with role and model.

        Args:
            role: Role defining agent behavior (prompts, tools, context)
            model: Language model instance, or None to use Claude Code's default model
            additional_tools: Extra tools to add beyond those defined by the role
            custom_instructions: User-defined instructions to append to the base system prompt
        """
        self.role = role
        self.model = model
        self.additional_tools = additional_tools or []
        self.custom_instructions = custom_instructions

    def get_tools(self) -> list[Tool]:
        """Get all tools for this agent (role tools + additional tools)."""
        return self.role.get_tools() + self.additional_tools

    def get_full_system_prompt(self) -> str:
        """Get the complete system prompt including custom instructions.

        Combines the role's base system prompt with user-defined custom instructions
        (if any) using a clear separator.

        Returns:
            Complete system prompt string
        """
        base_prompt = self.role.get_system_prompt() + SHARED_PROMPT_SUFFIX
        if self.custom_instructions:
            return base_prompt + CUSTOM_INSTRUCTIONS_SEPARATOR + self.custom_instructions
        return base_prompt

    async def run(self, prompt_or_approvals: str | ToolApprovals) -> list[ConversationEvent]:
        """Execute agent with either a user message or tool approval results.

        Args:
            prompt_or_approvals: Either a user message string or tool approval results

        Returns:
            List of conversation events generated during agent execution
        """
        events: list[ConversationEvent] = []

        # Collect all events from stream
        async for event in self.stream_events(prompt_or_approvals):
            events.append(event)

        return events

    @abstractmethod
    async def stream_events(self, prompt_or_approvals: str | ToolApprovals) -> AsyncIterator[ConversationEvent]:
        """Stream conversation events from agent execution.

        Args:
            prompt_or_approvals: Either a user message string or tool approval results

        Yields:
            Conversation events as they are generated during agent execution
        """
        if False:
            yield  # type: ignore[unreachable]  # Required for async generator type inference
