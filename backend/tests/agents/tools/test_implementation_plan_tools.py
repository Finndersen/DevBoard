"""Tests for implementation plan tools."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.events import SystemEventType
from devboard.agents.exceptions import AgentInterruptedError
from devboard.agents.language_models import ModelType
from devboard.agents.tools.implementation_plan_tools import (
    StepInput,
    create_execute_implementation_step_tool,
    create_get_implementation_plan_overview_tool,
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
    def mock_execution_manager(self) -> Mock:
        return Mock()

    @pytest.fixture
    def execute_step_tool(self, mock_task: Mock, mock_plan_service: Mock, mock_execution_manager: Mock) -> Mock:
        mock_task.implementation_plan_structured = Mock(spec=ImplementationPlan)
        return create_execute_implementation_step_tool(
            task=mock_task,
            plan_service=mock_plan_service,
            agent_config_service=Mock(),
            conversation_repo=Mock(),
            parent_conversation_id=None,
            working_dir="/test/working_dir",
            execution_manager=mock_execution_manager,
        )

    def _make_step(self, status: ImplementationStepStatus) -> Mock:
        step = Mock(spec=ImplementationStep)
        step.status = status
        step.step_number = 1
        step.conversation_id = None
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
    async def test_allows_running_step_without_conversation_id(self, execute_step_tool: Mock, mock_plan_service: Mock):
        """A step in RUNNING with no conversation_id is allowed (stale RUNNING from startup)."""
        step = self._make_step(ImplementationStepStatus.RUNNING)
        step.conversation_id = None
        mock_plan_service.get_step_by_number.return_value = step

        # Should pass status validation, then fail at sub-agent call
        with pytest.raises((TypeError, Exception)):
            await execute_step_tool.function(step_number=1)

        mock_plan_service.set_step_status.assert_any_call(step, status=ImplementationStepStatus.RUNNING)

    @pytest.mark.asyncio
    async def test_rejects_complete_step(self, execute_step_tool: Mock, mock_plan_service: Mock):
        step = self._make_step(ImplementationStepStatus.COMPLETE)
        mock_plan_service.get_step_by_number.return_value = step

        with pytest.raises(ModelRetry, match="expected 'pending', 'running', 'failed', or 'interrupted'"):
            await execute_step_tool.function(step_number=1)

    @pytest.mark.asyncio
    async def test_rejects_skipped_step(self, execute_step_tool: Mock, mock_plan_service: Mock):
        step = self._make_step(ImplementationStepStatus.SKIPPED)
        mock_plan_service.get_step_by_number.return_value = step

        with pytest.raises(ModelRetry, match="expected 'pending', 'running', 'failed', or 'interrupted'"):
            await execute_step_tool.function(step_number=1)

    @pytest.mark.asyncio
    async def test_allows_retry_of_stale_running_step(
        self, execute_step_tool: Mock, mock_plan_service: Mock, mock_execution_manager: Mock
    ):
        """A step in RUNNING status with no active execution can be retried without force_run."""
        step = self._make_step(ImplementationStepStatus.RUNNING)
        step.conversation_id = 42
        mock_plan_service.get_step_by_number.return_value = step
        # execution_manager.has_active_execution returns False (no active execution)
        mock_execution_manager.has_active_execution.return_value = False

        # Should pass the active execution check and status validation,
        # then fail at the sub-agent call (TypeError from mocks) to confirm it got past.
        with pytest.raises((TypeError, Exception)):
            await execute_step_tool.function(step_number=1)

        mock_plan_service.set_step_status.assert_any_call(step, status=ImplementationStepStatus.RUNNING)

    @pytest.mark.asyncio
    async def test_rejects_running_step_with_active_execution_even_with_force_run(
        self, execute_step_tool: Mock, mock_plan_service: Mock, mock_execution_manager: Mock
    ):
        """A step in RUNNING status with active execution is rejected even if force_run=True."""
        step = self._make_step(ImplementationStepStatus.RUNNING)
        step.conversation_id = 99
        mock_plan_service.get_step_by_number.return_value = step
        # execution_manager.has_active_execution returns True (active execution)
        mock_execution_manager.has_active_execution.return_value = True

        with pytest.raises(ModelRetry, match="Step 1 is already running"):
            await execute_step_tool.function(step_number=1, force_run=True)


class TestExecuteImplementationStepConversationFlow:
    """Tests for conversation_id tracking in execute_implementation_step."""

    @pytest.fixture
    def mock_agent_config_service(self) -> Mock:
        return Mock()

    @pytest.fixture
    def mock_conversation_repo(self) -> Mock:
        return Mock()

    @pytest.fixture
    def mock_execution_manager(self) -> Mock:
        return Mock()

    @pytest.fixture
    def execute_step_tool(
        self,
        mock_task: Mock,
        mock_plan_service: Mock,
        mock_agent_config_service: Mock,
        mock_conversation_repo: Mock,
        mock_execution_manager: Mock,
    ) -> Mock:
        mock_task.implementation_plan_structured = Mock(spec=ImplementationPlan)
        return create_execute_implementation_step_tool(
            task=mock_task,
            plan_service=mock_plan_service,
            agent_config_service=mock_agent_config_service,
            conversation_repo=mock_conversation_repo,
            parent_conversation_id=None,
            working_dir="/test/working_dir",
            execution_manager=mock_execution_manager,
            task_git_service=Mock(),
        )

    def _make_step(
        self,
        step_type: ImplementationStepType = ImplementationStepType.CODE_CHANGE,
        conversation_id: int | None = None,
        model_type: ModelType | None = None,
    ) -> Mock:
        step = Mock(spec=ImplementationStep)
        step.status = ImplementationStepStatus.PENDING
        step.step_number = 1
        step.type = step_type
        step.title = "Test step"
        step.details = "Do the thing"
        step.conversation_id = conversation_id
        step.model_type = model_type
        return step

    @pytest.mark.asyncio
    async def test_new_step_creates_conversation_and_calls_set_step_conversation(
        self, execute_step_tool: Mock, mock_plan_service: Mock, mock_execution_manager: Mock
    ):
        """For a new step (no conversation_id), a conversation is created and set_step_conversation called."""
        step = self._make_step()
        mock_plan_service.get_step_by_number.return_value = step

        mock_conversation = Mock()
        mock_conversation.id = 42
        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Done"
        mock_sub_agent_result.conversation_id = 42
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        with patch(
            "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
            return_value=mock_conversation,
        ) as mock_create:
            await execute_step_tool.function(step_number=1)

        mock_create.assert_called_once()
        mock_plan_service.set_step_conversation.assert_called_once_with(step, 42)
        call_kwargs = mock_execution_manager.run_sub_agent_execution.call_args.kwargs
        assert call_kwargs["conversation"] is mock_conversation

    @pytest.mark.asyncio
    async def test_run_sub_agent_execution_called_with_correct_args(
        self,
        execute_step_tool: Mock,
        mock_plan_service: Mock,
        mock_conversation_repo: Mock,
        mock_agent_config_service: Mock,
        mock_execution_manager: Mock,
    ):
        """run_sub_agent_execution receives the conversation object and correct repo/config."""
        step = self._make_step()
        mock_plan_service.get_step_by_number.return_value = step

        mock_conversation = Mock()
        mock_conversation.id = 7
        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Done"
        mock_sub_agent_result.conversation_id = 7
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        with patch(
            "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
            return_value=mock_conversation,
        ):
            await execute_step_tool.function(step_number=1)

        call_kwargs = mock_execution_manager.run_sub_agent_execution.call_args.kwargs
        assert call_kwargs["conversation"] is mock_conversation
        assert call_kwargs["conversation_repo"] is mock_conversation_repo
        assert call_kwargs["agent_config_service"] is mock_agent_config_service
        assert call_kwargs["working_dir"] == "/test/working_dir"

    @pytest.mark.asyncio
    async def test_existing_step_resumes_conversation(
        self,
        execute_step_tool: Mock,
        mock_plan_service: Mock,
        mock_conversation_repo: Mock,
        mock_execution_manager: Mock,
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
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        with patch(
            "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
        ) as mock_create:
            await execute_step_tool.function(step_number=1)

        mock_create.assert_not_called()
        mock_plan_service.set_step_conversation.assert_not_called()
        mock_conversation_repo.get_by_id.assert_called_with(99)
        call_kwargs = mock_execution_manager.run_sub_agent_execution.call_args.kwargs
        assert call_kwargs["conversation"] is existing_conv
        assert "Resume" in call_kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_agent_interrupted_error_sets_interrupted_status(
        self,
        execute_step_tool: Mock,
        mock_plan_service: Mock,
        mock_execution_manager: Mock,
    ):
        """When sub-agent raises AgentInterruptedError, step status is set to INTERRUPTED and error propagates."""
        step = self._make_step()
        mock_plan_service.get_step_by_number.return_value = step

        mock_conversation = Mock()
        mock_conversation.id = 10
        mock_execution_manager.run_sub_agent_execution = AsyncMock(side_effect=AgentInterruptedError())

        with patch(
            "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
            return_value=mock_conversation,
        ):
            with pytest.raises(AgentInterruptedError):
                await execute_step_tool.function(step_number=1)

        mock_plan_service.set_step_status.assert_any_call(
            step, status=ImplementationStepStatus.INTERRUPTED, outcome="Step interrupted by user."
        )


class TestExecuteImplementationStepBroadcastEvent:
    """Tests that IMPLEMENTATION_STEP_STARTED is emitted via execution_manager.broadcast_event."""

    PARENT_CONV_ID = 10

    @pytest.fixture
    def mock_execution_manager(self) -> Mock:
        mgr = Mock()
        mgr.broadcast_event = AsyncMock()
        return mgr

    @pytest.fixture
    def execute_step_tool_with_parent(
        self,
        mock_task: Mock,
        mock_plan_service: Mock,
        mock_execution_manager: Mock,
    ) -> Mock:
        mock_task.id = 5
        mock_task.implementation_plan_structured = Mock(spec=ImplementationPlan)
        return create_execute_implementation_step_tool(
            task=mock_task,
            plan_service=mock_plan_service,
            agent_config_service=Mock(),
            conversation_repo=Mock(),
            parent_conversation_id=self.PARENT_CONV_ID,
            working_dir="/test/working_dir",
            execution_manager=mock_execution_manager,
            task_git_service=Mock(),
        )

    def _make_step(self, conversation_id: int | None = None) -> Mock:
        step = Mock(spec=ImplementationStep)
        step.status = ImplementationStepStatus.PENDING
        step.step_number = 1
        step.type = ImplementationStepType.CODE_CHANGE
        step.title = "Test step"
        step.details = "Do the thing"
        step.conversation_id = conversation_id
        step.model_type = None
        step.dependencies = []
        return step

    @pytest.mark.asyncio
    async def test_new_step_emits_implementation_step_started(
        self,
        execute_step_tool_with_parent: Mock,
        mock_plan_service: Mock,
        mock_execution_manager: Mock,
        mock_task: Mock,
    ):
        """IMPLEMENTATION_STEP_STARTED is broadcast on parent_conversation_id for a new step."""
        step = self._make_step()
        mock_plan_service.get_step_by_number.return_value = step

        mock_conversation = Mock()
        mock_conversation.id = 42
        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Done"
        mock_sub_agent_result.conversation_id = 42
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        with patch(
            "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
            return_value=mock_conversation,
        ):
            await execute_step_tool_with_parent.function(step_number=1)

        mock_execution_manager.broadcast_event.assert_awaited_once()
        broadcast_conv_id, broadcast_event = mock_execution_manager.broadcast_event.call_args.args
        assert broadcast_conv_id == self.PARENT_CONV_ID
        assert broadcast_event.sub_type == SystemEventType.IMPLEMENTATION_STEP_STARTED
        assert broadcast_event.data == {"task_id": mock_task.id, "step_number": 1, "conversation_id": 42}

    @pytest.mark.asyncio
    async def test_resuming_step_emits_implementation_step_started(
        self,
        execute_step_tool_with_parent: Mock,
        mock_plan_service: Mock,
        mock_execution_manager: Mock,
        mock_task: Mock,
    ):
        """IMPLEMENTATION_STEP_STARTED is broadcast on parent_conversation_id when resuming an existing step."""
        existing_conv = Mock()
        existing_conv.id = 99
        step = self._make_step(conversation_id=99)
        step.status = ImplementationStepStatus.FAILED
        mock_plan_service.get_step_by_number.return_value = step

        # Wire conversation_repo to return the existing conversation
        # We need to reach the conversation_repo inside the tool's closure
        # The tool was created with Mock() for conversation_repo; set up get_by_id on mock_plan_service's repo
        # Actually the conversation_repo is a separate Mock passed to create_execute_implementation_step_tool
        # We need to inject it — easiest is to re-create the tool with a proper mock_conversation_repo
        mock_conversation_repo = Mock()
        mock_conversation_repo.get_by_id.return_value = existing_conv

        tool_with_repo = create_execute_implementation_step_tool(
            task=mock_task,
            plan_service=mock_plan_service,
            agent_config_service=Mock(),
            conversation_repo=mock_conversation_repo,
            parent_conversation_id=self.PARENT_CONV_ID,
            working_dir="/test/working_dir",
            execution_manager=mock_execution_manager,
            task_git_service=Mock(),
        )

        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Resumed"
        mock_sub_agent_result.conversation_id = 99
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        await tool_with_repo.function(step_number=1)

        mock_execution_manager.broadcast_event.assert_awaited_once()
        broadcast_conv_id, broadcast_event = mock_execution_manager.broadcast_event.call_args.args
        assert broadcast_conv_id == self.PARENT_CONV_ID
        assert broadcast_event.sub_type == SystemEventType.IMPLEMENTATION_STEP_STARTED
        assert broadcast_event.data == {"task_id": mock_task.id, "step_number": 1, "conversation_id": 99}

    @pytest.mark.asyncio
    async def test_no_event_when_no_parent_conversation(
        self,
        mock_task: Mock,
        mock_plan_service: Mock,
    ):
        """No broadcast_event call when parent_conversation_id is None."""
        mock_task.id = 5
        mock_task.implementation_plan_structured = Mock(spec=ImplementationPlan)
        mock_execution_manager = Mock()
        mock_execution_manager.broadcast_event = AsyncMock()

        tool = create_execute_implementation_step_tool(
            task=mock_task,
            plan_service=mock_plan_service,
            agent_config_service=Mock(),
            conversation_repo=Mock(),
            parent_conversation_id=None,
            working_dir="/test/working_dir",
            execution_manager=mock_execution_manager,
            task_git_service=Mock(),
        )

        step = self._make_step()
        mock_plan_service.get_step_by_number.return_value = step

        mock_conversation = Mock()
        mock_conversation.id = 7
        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Done"
        mock_sub_agent_result.conversation_id = 7
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        with patch(
            "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
            return_value=mock_conversation,
        ):
            await tool.function(step_number=1)

        mock_execution_manager.broadcast_event.assert_not_awaited()


class TestStepInputModelType:
    """Tests for model_type field on StepInput."""

    def test_step_input_accepts_fast_model_type(self):
        step = StepInput(title="Test", type="code_change", details="Do it", model_type="fast")
        assert step.model_type == "fast"

    def test_step_input_accepts_standard_model_type(self):
        step = StepInput(title="Test", type="code_review", details="Review it", model_type="standard")
        assert step.model_type == "standard"

    def test_step_input_accepts_advanced_model_type(self):
        step = StepInput(title="Test", type="code_review", details="Review it", model_type="advanced")
        assert step.model_type == "advanced"

    def test_step_input_model_type_defaults_to_none(self):
        step = StepInput(title="Test", type="validation", details="Run tests")
        assert step.model_type is None

    def test_step_input_model_dump_includes_model_type(self):
        step = StepInput(title="Test", type="code_change", details="Do it", model_type="fast")
        data = step.model_dump()
        assert data == {
            "title": "Test",
            "type": "code_change",
            "model_type": "fast",
            "dependencies": [],
            "details": "Do it",
        }


class TestExecuteImplementationStepModelType:
    """Tests that execute_implementation_step passes model_type to create_sub_agent_conversation."""

    @pytest.fixture
    def mock_plan_service(self) -> Mock:
        return Mock(spec=TaskImplementationPlanService)

    @pytest.fixture
    def mock_task(self) -> Mock:
        task = Mock(spec=Task)
        task.implementation_plan_structured = Mock(spec=ImplementationPlan)
        return task

    def _make_step(self, model_type: ModelType | None = None) -> Mock:
        step = Mock(spec=ImplementationStep)
        step.status = ImplementationStepStatus.PENDING
        step.step_number = 1
        step.type = ImplementationStepType.CODE_CHANGE
        step.title = "Test step"
        step.details = "Do the thing"
        step.conversation_id = None
        step.model_type = model_type
        step.dependencies = []
        return step

    @pytest.mark.asyncio
    async def test_passes_model_type_to_create_sub_agent_conversation(self, mock_task: Mock, mock_plan_service: Mock):
        """When step has a model_type, it is passed to create_sub_agent_conversation."""
        mock_execution_manager = Mock()
        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Done"
        mock_sub_agent_result.conversation_id = 42
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        tool = create_execute_implementation_step_tool(
            task=mock_task,
            plan_service=mock_plan_service,
            agent_config_service=Mock(),
            conversation_repo=Mock(),
            parent_conversation_id=None,
            working_dir="/test/working_dir",
            execution_manager=mock_execution_manager,
            task_git_service=Mock(),
        )

        step = self._make_step(model_type=ModelType.FAST)
        mock_plan_service.get_step_by_number.return_value = step

        mock_conversation = Mock()
        mock_conversation.id = 42

        with patch(
            "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
            return_value=mock_conversation,
        ) as mock_create:
            await tool.function(step_number=1)

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model_type"] == ModelType.FAST

    @pytest.mark.asyncio
    async def test_passes_none_model_type_when_step_has_no_model_type(self, mock_task: Mock, mock_plan_service: Mock):
        """When step.model_type is None, model_type=None is passed to create_sub_agent_conversation."""
        mock_execution_manager = Mock()
        mock_sub_agent_result = Mock()
        mock_sub_agent_result.result = "Done"
        mock_sub_agent_result.conversation_id = 42
        mock_execution_manager.run_sub_agent_execution = AsyncMock(return_value=mock_sub_agent_result)

        tool = create_execute_implementation_step_tool(
            task=mock_task,
            plan_service=mock_plan_service,
            agent_config_service=Mock(),
            conversation_repo=Mock(),
            parent_conversation_id=None,
            working_dir="/test/working_dir",
            execution_manager=mock_execution_manager,
            task_git_service=Mock(),
        )

        step = self._make_step(model_type=None)
        mock_plan_service.get_step_by_number.return_value = step

        mock_conversation = Mock()
        mock_conversation.id = 42

        with patch(
            "devboard.agents.tools.implementation_plan_tools.create_sub_agent_conversation",
            return_value=mock_conversation,
        ) as mock_create:
            await tool.function(step_number=1)

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model_type"] is None


class TestGetImplementationPlanOverviewTool:
    """Tests for get_implementation_plan_overview tool with conversation IDs."""

    def test_returns_plan_overview_without_steps(self, mock_task: Mock):
        """get_implementation_plan_overview returns plan overview when no steps exist."""
        plan = Mock(spec=ImplementationPlan)
        plan.overview = "This is the plan overview"
        plan.steps = []

        mock_task.implementation_plan_structured = plan

        tool = create_get_implementation_plan_overview_tool(mock_task)
        result = tool.function()

        assert "Overview: This is the plan overview" in result
        assert "Steps:" in result

    def test_includes_conversation_id_in_output(self, mock_task: Mock):
        """get_implementation_plan_overview includes conversation_id when present."""
        step1 = Mock(spec=ImplementationStep)
        step1.step_number = 1
        step1.title = "First Step"
        step1.type = ImplementationStepType.CODE_CHANGE
        step1.status = ImplementationStepStatus.PENDING
        step1.dependencies = []
        step1.conversation_id = 99

        step2 = Mock(spec=ImplementationStep)
        step2.step_number = 2
        step2.title = "Second Step"
        step2.type = ImplementationStepType.CODE_REVIEW
        step2.status = ImplementationStepStatus.COMPLETE
        step2.dependencies = [1]
        step2.conversation_id = 100

        plan = Mock(spec=ImplementationPlan)
        plan.overview = None
        plan.steps = [step1, step2]

        mock_task.implementation_plan_structured = plan

        tool = create_get_implementation_plan_overview_tool(mock_task)
        result = tool.function()

        assert "1. [pending] First Step [code_change]" in result
        assert "conv_id=99" in result
        assert "2. [complete] Second Step [code_review] (depends on: 1)" in result
        assert "conv_id=100" in result

    def test_excludes_conversation_id_when_none(self, mock_task: Mock):
        """get_implementation_plan_overview does not include conv_id when conversation_id is None."""
        step = Mock(spec=ImplementationStep)
        step.step_number = 1
        step.title = "Test Step"
        step.type = ImplementationStepType.CODE_CHANGE
        step.status = ImplementationStepStatus.PENDING
        step.dependencies = []
        step.conversation_id = None

        plan = Mock(spec=ImplementationPlan)
        plan.overview = None
        plan.steps = [step]

        mock_task.implementation_plan_structured = plan

        tool = create_get_implementation_plan_overview_tool(mock_task)
        result = tool.function()

        assert "1. [pending] Test Step [code_change]" in result
        assert "conv_id=" not in result

    def test_raises_when_no_plan(self, mock_task: Mock):
        """get_implementation_plan_overview raises when no plan exists."""
        mock_task.implementation_plan_structured = None

        tool = create_get_implementation_plan_overview_tool(mock_task)

        with pytest.raises(ModelRetry, match="No implementation plan exists"):
            tool.function()

    def test_docstring_mentions_inspect_conversation(self, mock_task: Mock):
        """get_implementation_plan_overview docstring mentions inspect_conversation tool."""
        tool = create_get_implementation_plan_overview_tool(mock_task)
        docstring = tool.function.__doc__

        assert docstring is not None
        assert "inspect_conversation" in docstring.lower() or "conversation" in docstring.lower()
