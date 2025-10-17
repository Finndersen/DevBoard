"""Tests for PromptActionService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from devboard.api.schemas.agent_conversation import PromptResponse
from devboard.services.prompt_action_service import PromptActionNotFoundError, PromptActionService


@pytest.fixture
def mock_conversation_service():
    """Mock BaseAgentConversationService."""
    service = MagicMock()
    service.send_message = AsyncMock(
        return_value=PromptResponse(
            type="message",
            message={"role": "agent", "text_content": "Mock response", "timestamp": "2024-01-01T00:00:00Z"},
            tool_requests=None,
        )
    )
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
    async def test_execute_action_success(self, prompt_action_service, mock_conversation_service):
        """Test executing a valid action."""
        result = await prompt_action_service.execute_action("task.create_implementation_plan")

        assert result.type == "message"
        assert result.message is not None
        # Verify conversation service was called with the prompt template
        mock_conversation_service.send_message.assert_called_once()
        call_args = mock_conversation_service.send_message.call_args
        assert "implementation plan" in call_args[1]["message"].lower()

    @pytest.mark.asyncio
    async def test_execute_action_not_found(self, prompt_action_service):
        """Test executing a non-existent action raises error."""
        with pytest.raises(PromptActionNotFoundError, match="nonexistent.action"):
            await prompt_action_service.execute_action("nonexistent.action")
