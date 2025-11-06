"""Tests for PromptActionService."""

from unittest.mock import MagicMock

import pytest

from devboard.agents.events import TextMessage
from devboard.services.prompt_action_service import PromptActionNotFoundError, PromptActionService


@pytest.fixture
def mock_conversation_service():
    """Mock BaseAgentConversationService."""

    async def mock_stream_events():
        yield TextMessage(
            event_type="message",
            role="agent",
            text_content="Mock response",
            timestamp="2024-01-01T00:00:00Z",
        )

    service = MagicMock()
    service.stream_events_for_message_or_approval = MagicMock(return_value=mock_stream_events())
    return service


@pytest.fixture
def prompt_action_service(mock_conversation_service):
    """Create PromptActionService with mocked dependencies."""
    return PromptActionService(conversation_service=mock_conversation_service)


class TestPromptActionService:
    """Tests for PromptActionService."""

    def test_get_action_success(self, prompt_action_service):
        """Test getting an existing action."""
        action = prompt_action_service.get_action("task.create_implementation_plan")

        assert action is not None
        assert action.key == "task.create_implementation_plan"
        assert "implementation plan" in action.prompt_template.lower()

    def test_get_action_not_found(self, prompt_action_service):
        """Test getting a non-existent action returns None."""
        action = prompt_action_service.get_action("nonexistent.action")

        assert action is None

    @pytest.mark.asyncio
    async def test_stream_action_success(self, prompt_action_service, mock_conversation_service):
        """Test streaming a valid action."""
        events = []
        async for event in prompt_action_service.stream_action("task.create_implementation_plan"):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], TextMessage)
        assert events[0].role == "agent"
        # Verify conversation service was called with the prompt template
        mock_conversation_service.stream_events_for_message_or_approval.assert_called_once()
        call_args = mock_conversation_service.stream_events_for_message_or_approval.call_args
        assert "implementation plan" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_stream_action_not_found(self, prompt_action_service):
        """Test streaming a non-existent action raises error."""
        with pytest.raises(PromptActionNotFoundError, match="nonexistent.action"):
            async for _ in prompt_action_service.stream_action("nonexistent.action"):
                pass
