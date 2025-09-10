"""Tests for TaskConversationService."""

from unittest.mock import AsyncMock

import pytest

from devboard.services.task_conversation import TaskConversationService


class TestTaskConversationService:
    """Test TaskConversationService functionality."""

    @pytest.fixture
    def task_conversation_service(self):
        """Create TaskConversationService instance."""
        return TaskConversationService()

    @pytest.fixture
    def mock_agent_service(self):
        """Mock agent service."""
        mock_service = AsyncMock()
        mock_service.process_message_with_state = AsyncMock(return_value=("result", None))
        mock_service.process_tool_approval_with_state = AsyncMock(return_value="approval_result")
        return mock_service

    async def test_process_with_agent_success(self, task_conversation_service, mock_agent_service):
        """Test _process_with_agent successfully calls agent service."""
        message = "Test message"
        history = []
        kwargs = {
            "entity_id": 123,
            "task_title": "Test Task",
            "task_description": "Test description",
            "task_implementation_plan": "Test plan",
            "task_state": "Designing",
            "project_id": 456,
        }

        result, deferred = await task_conversation_service._process_with_agent(
            mock_agent_service, message, history, **kwargs
        )

        assert result == "result"
        assert deferred is None

        # Verify the agent service was called with correct parameters
        mock_agent_service.process_message_with_state.assert_called_once_with(
            task_id=123,
            message_history=history,
            user_message=message,
            task_title="Test Task",
            task_description="Test description",
            task_implementation_plan="Test plan",
            task_state="Designing",
            project_id=456,
        )

    async def test_process_with_agent_with_deferred_requests(
        self, task_conversation_service, mock_agent_service
    ):
        """Test _process_with_agent with deferred tool requests."""
        mock_agent_service.process_message_with_state.return_value = ("result", "deferred_requests")

        message = "Test message"
        history = []
        kwargs = {"entity_id": 123, "task_title": "Test Task"}

        result, deferred = await task_conversation_service._process_with_agent(
            mock_agent_service, message, history, **kwargs
        )

        assert result == "result"
        assert deferred == "deferred_requests"

    async def test_process_with_agent_missing_entity_id(
        self, task_conversation_service, mock_agent_service
    ):
        """Test _process_with_agent with missing entity_id."""
        message = "Test message"
        history = []
        kwargs = {"task_title": "Test Task"}  # No entity_id

        result, deferred = await task_conversation_service._process_with_agent(
            mock_agent_service, message, history, **kwargs
        )

        # Should pass None as task_id when entity_id is missing
        mock_agent_service.process_message_with_state.assert_called_once_with(
            task_id=None,
            message_history=history,
            user_message=message,
            task_title="Test Task",
        )

    async def test_process_tool_approval_with_agent_success(
        self, task_conversation_service, mock_agent_service
    ):
        """Test _process_tool_approval_with_agent successfully calls agent service."""
        deferred_results = "mock_deferred_results"
        history = []
        kwargs = {
            "entity_id": 123,
            "task_title": "Test Task",
            "task_description": "Test description",
            "task_implementation_plan": "Test plan",
            "task_state": "Planning",
            "project_id": 456,
        }

        result = await task_conversation_service._process_tool_approval_with_agent(
            mock_agent_service, deferred_results, history, **kwargs
        )

        assert result == "approval_result"

        # Verify the agent service was called with correct parameters
        mock_agent_service.process_tool_approval_with_state.assert_called_once_with(
            task_id=123,
            deferred_results=deferred_results,
            message_history=history,
            task_title="Test Task",
            task_description="Test description",
            task_implementation_plan="Test plan",
            task_state="Planning",
            project_id=456,
        )

    async def test_process_tool_approval_with_agent_missing_entity_id(
        self, task_conversation_service, mock_agent_service
    ):
        """Test _process_tool_approval_with_agent with missing entity_id."""
        deferred_results = "mock_deferred_results"
        history = []
        kwargs = {"task_title": "Test Task"}  # No entity_id

        await task_conversation_service._process_tool_approval_with_agent(
            mock_agent_service, deferred_results, history, **kwargs
        )

        # Should pass None as task_id when entity_id is missing
        mock_agent_service.process_tool_approval_with_state.assert_called_once_with(
            task_id=None,
            deferred_results=deferred_results,
            message_history=history,
            task_title="Test Task",
        )

    async def test_process_with_agent_exception_propagation(
        self, task_conversation_service, mock_agent_service
    ):
        """Test that exceptions from agent service are propagated."""
        mock_agent_service.process_message_with_state.side_effect = Exception("Agent error")

        with pytest.raises(Exception, match="Agent error"):
            await task_conversation_service._process_with_agent(
                mock_agent_service, "test message", [], entity_id=123
            )

    async def test_process_tool_approval_exception_propagation(
        self, task_conversation_service, mock_agent_service
    ):
        """Test that exceptions from agent service are propagated in tool approval."""
        mock_agent_service.process_tool_approval_with_state.side_effect = Exception("Approval error")

        with pytest.raises(Exception, match="Approval error"):
            await task_conversation_service._process_tool_approval_with_agent(
                mock_agent_service, "deferred_results", [], entity_id=123
            )

    def test_inheritance_from_agent_conversation_service(self, task_conversation_service):
        """Test that TaskConversationService inherits from AgentConversationService."""
        from devboard.services.agent_conversation import AgentConversationService

        assert isinstance(task_conversation_service, AgentConversationService)

    def test_service_instance_exists(self):
        """Test that the global service instance exists."""
        from devboard.services.task_conversation import task_conversation_service

        assert isinstance(task_conversation_service, TaskConversationService)
