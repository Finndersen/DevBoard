"""Base agent interface for all agent implementations."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from devboard.agents.events import ConversationEvent
from devboard.agents.language_models import LanguageModel
from devboard.agents.roles.base import Role
from devboard.api.schemas.agent_conversation import ToolApprovals


class BaseAgent(ABC):
    """Abstract base class for all agent implementations.

    Provides a unified interface for agent execution with consistent
    method signatures across different engine implementations.
    """

    def __init__(
        self,
        role: Role,
        model: LanguageModel | None,
    ):
        """Initialize base agent with role and model.

        Args:
            role: Role defining agent behavior (prompts, tools, context)
            model: Language model instance, or None to use Claude Code's default model
        """
        self.role = role
        self.model = model

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
