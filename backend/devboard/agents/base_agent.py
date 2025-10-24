"""Base agent interface for all agent implementations."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from devboard.agents.events import ConversationEvent
from devboard.api.schemas.agent_conversation import ToolApprovals


class BaseAgent(ABC):
    """Abstract base class for all agent implementations.

    Provides a unified interface for agent execution with consistent
    method signatures across different engine implementations.
    """

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
        pass
