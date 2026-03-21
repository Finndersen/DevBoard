"""Tests for implementation plan tools."""

from unittest.mock import Mock

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

        mock_plan_service.set_step_status.assert_any_call(step, ImplementationStepStatus.RUNNING)

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
