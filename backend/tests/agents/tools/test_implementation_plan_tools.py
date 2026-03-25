"""Tests for implementation plan tools."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.implementation_plan_tools import (
    create_execute_implementation_step_tool,
    create_read_implementation_step_details_tool,
)
from devboard.db.models.implementation_plan import (
    ImplementationPlan,
    ImplementationStep,
    ImplementationStepStatus,
    ImplementationStepType,
)
from devboard.db.models.task import Task
from devboard.services.task_implementation_plan import TaskImplementationPlanService


@pytest.fixture
def mock_task() -> Mock:
    return Mock(spec=Task)


@pytest.fixture
def mock_plan_service() -> Mock:
    return Mock(spec=TaskImplementationPlanService)


class TestReadImplementationStepDetailsTool:
    def test_returns_step_details(self, mock_task: Mock, mock_plan_service: Mock):
        plan = Mock(spec=ImplementationPlan)
        mock_task.implementation_plan_structured = plan
        step = Mock(spec=ImplementationStep)
        step.details = "Do the thing"
        mock_plan_service.get_step_by_number.return_value = step

        tool = create_read_implementation_step_details_tool(mock_task, mock_plan_service)
        result = tool.function(step_number=1)

        assert result == "Do the thing"
        mock_plan_service.get_step_by_number.assert_called_once_with(plan, 1)

    def test_raises_when_no_plan(self, mock_task: Mock, mock_plan_service: Mock):
        mock_task.implementation_plan_structured = None

        tool = create_read_implementation_step_details_tool(mock_task, mock_plan_service)

        with pytest.raises(ModelRetry, match="No implementation plan exists"):
            tool.function(step_number=1)

    def test_raises_when_step_not_found(self, mock_task: Mock, mock_plan_service: Mock):
        plan = Mock(spec=ImplementationPlan)
        mock_task.implementation_plan_structured = plan
        mock_plan_service.get_step_by_number.return_value = None

        tool = create_read_implementation_step_details_tool(mock_task, mock_plan_service)

        with pytest.raises(ModelRetry, match="Step 5 not found"):
            tool.function(step_number=5)


class TestExecuteImplementationStepStatusValidation:
    """Tests for status validation in execute_implementation_step."""

    @pytest.fixture
    def execute_step_tool(self, mock_task: Mock, mock_plan_service: Mock) -> Mock:
        mock_task.implementation_plan_structured = Mock(spec=ImplementationPlan)
        return create_execute_implementation_step_tool(
            task=mock_task,
            plan_service=mock_plan_service,
            agent_config_service=Mock(),
            conversation_repo=Mock(),
            parent_conversation_id=None,
            working_dir="/test/working_dir",
        )

    def _make_step(self, status: ImplementationStepStatus) -> Mock:
        step = Mock(spec=ImplementationStep)
        step.status = status
        step.step_number = 1
        return step

    @pytest.mark.asyncio
    async def test_allows_retry_of_failed_step(self, execute_step_tool: Mock, mock_plan_service: Mock):
        step = self._make_step(ImplementationStepStatus.FAILED)
        mock_plan_service.get_step_by_number.return_value = step

        # Should pass status validation and proceed to set RUNNING.
        # We let it fail at the sub-agent call (TypeError from mocks) to confirm
        # it got past the status gate.
        with pytest.raises((TypeError, Exception)):
            await execute_step_tool.function(step_number=1)

        mock_plan_service.set_step_status.assert_any_call(step, status=ImplementationStepStatus.RUNNING)

    @pytest.mark.asyncio
    async def test_rejects_running_step(self, execute_step_tool: Mock, mock_plan_service: Mock):
        step = self._make_step(ImplementationStepStatus.RUNNING)
        mock_plan_service.get_step_by_number.return_value = step

        with pytest.raises(ModelRetry, match="expected 'pending' or 'failed'"):
            await execute_step_tool.function(step_number=1)

    @pytest.mark.asyncio
    async def test_rejects_complete_step(self, execute_step_tool: Mock, mock_plan_service: Mock):
        step = self._make_step(ImplementationStepStatus.COMPLETE)
        mock_plan_service.get_step_by_number.return_value = step

        with pytest.raises(ModelRetry, match="expected 'pending' or 'failed'"):
            await execute_step_tool.function(step_number=1)

    @pytest.mark.asyncio
    async def test_rejects_skipped_step(self, execute_step_tool: Mock, mock_plan_service: Mock):
        step = self._make_step(ImplementationStepStatus.SKIPPED)
        mock_plan_service.get_step_by_number.return_value = step

        with pytest.raises(ModelRetry, match="expected 'pending' or 'failed'"):
            await execute_step_tool.function(step_number=1)


class TestExecuteImplementationStepConversationFlow:
    """Tests for conversation_id tracking in execute_implementation_step."""

    @pytest.fixture
    def mock_agent_config_service(self) -> Mock:
        return Mock()

    @pytest.fixture
    def mock_conversation_repo(self) -> Mock:
        return Mock()

    @pytest.fixture
    def execute_step_tool(
        self,
        mock_task: Mock,
        mock_plan_service: Mock,
        mock_agent_config_service: Mock,
        mock_conversation_repo: Mock,
    ) -> Mock:
        mock_task.implementation_plan_structured = Mock(spec=ImplementationPlan)
        return create_execute_implementation_step_tool(
            task=mock_task,
            plan_service=mock_plan_service,
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conversation_repo,
            parent_conversation_id=None,
            working_dir="/test/working_dir",
            task_git_service=Mock(),
        )

    def _make_step(
        self,
        step_type: ImplementationStepType = ImplementationStepType.CODE_CHANGE,
        conversation_id: int | None = None,
    ) -> Mock:
        step = Mock(spec=ImplementationStep)
        step.status = ImplementationStepStatus.PENDING
        step.step_number = 1
        step.type = step_type
        step.title = "Test step"
        step.details = "Do the thing"
        step.conversation_id = conversation_id
        return step

    @pytest.mark.asyncio
    async def test_new_step_creates_conversation_and_calls_set_step_conversation(
        self, execute_step_tool: Mock, mock_plan_service: Mock
    ):
        """For a new step (no conversation_id), a conversation is created and set_step_conversation called."""
        step = self._make_step()
        mock_plan_service.get_step_by_number.return_value = step

        mock_conversation = Mock()
        mock_conversation.id = 42
        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Done"
        mock_sub_agent_result.conversation_id = 42

        with (
            patch(
                "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
                return_value=mock_conversation,
            ) as mock_create,
            patch(
                "devboard.agents.tools.implementation_plan_tools.execute_sub_agent_conversation",
                new_callable=AsyncMock,
                return_value=mock_sub_agent_result,
            ) as mock_execute,
        ):
            await execute_step_tool.function(step_number=1)

        mock_create.assert_called_once()
        mock_plan_service.set_step_conversation.assert_called_once_with(step, 42)
        call_kwargs = mock_execute.call_args.kwargs
        assert call_kwargs["conversation"] is mock_conversation

    @pytest.mark.asyncio
    async def test_execute_sub_agent_conversation_called_with_correct_args(
        self,
        execute_step_tool: Mock,
        mock_plan_service: Mock,
        mock_conversation_repo: Mock,
        mock_agent_config_service: Mock,
    ):
        """execute_sub_agent_conversation receives the conversation object and correct repo/config."""
        step = self._make_step()
        mock_plan_service.get_step_by_number.return_value = step

        mock_conversation = Mock()
        mock_conversation.id = 7
        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Done"
        mock_sub_agent_result.conversation_id = 7

        with (
            patch(
                "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
                return_value=mock_conversation,
            ),
            patch(
                "devboard.agents.tools.implementation_plan_tools.execute_sub_agent_conversation",
                new_callable=AsyncMock,
                return_value=mock_sub_agent_result,
            ) as mock_execute,
        ):
            await execute_step_tool.function(step_number=1)

        call_kwargs = mock_execute.call_args.kwargs
        assert call_kwargs["conversation"] is mock_conversation
        assert call_kwargs["conversation_repo"] is mock_conversation_repo
        assert call_kwargs["agent_config_service"] is mock_agent_config_service
        assert call_kwargs["working_dir"] == "/test/working_dir"

    @pytest.mark.asyncio
    async def test_existing_step_resumes_conversation(
        self, execute_step_tool: Mock, mock_plan_service: Mock, mock_conversation_repo: Mock
    ):
        """For a step with an existing conversation_id, it is resumed instead of creating a new one."""
        existing_conv = Mock()
        existing_conv.id = 99
        mock_conversation_repo.get_by_id.return_value = existing_conv
        step = self._make_step(conversation_id=99)
        step.status = ImplementationStepStatus.FAILED
        mock_plan_service.get_step_by_number.return_value = step

        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Resumed"
        mock_sub_agent_result.conversation_id = 99

        with (
            patch(
                "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
            ) as mock_create,
            patch(
                "devboard.agents.tools.implementation_plan_tools.execute_sub_agent_conversation",
                new_callable=AsyncMock,
                return_value=mock_sub_agent_result,
            ) as mock_execute,
        ):
            await execute_step_tool.function(step_number=1)

        mock_create.assert_not_called()
        mock_plan_service.set_step_conversation.assert_not_called()
        mock_conversation_repo.get_by_id.assert_called_with(99)
        assert mock_execute.call_args.kwargs["conversation"] is existing_conv
        assert "Resume" in mock_execute.call_args.kwargs["prompt"]
