"""Tests for the Task Planning Agent with restructured response and LLMService integration."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.api.schemas.task import DocumentEdit, TaskPlanningResponse
from devboard.services.context_assembly import (
    EagerContextData,
    OnDemandResourceInfo,
    ProjectContextData,
)
from devboard.services.task_planning_agent import (
    DocumentType,
    TaskContext,
    TaskPlanningAgentService,
    TaskState,
)


class TestTaskPlanningResponse:
    """Test the restructured TaskPlanningResponse schema."""

    def test_task_planning_response_creation(self):
        """Test creating TaskPlanningResponse with new structure."""
        response = TaskPlanningResponse(
            message="Task specification updated successfully.",
            task_specification_edits=[
                DocumentEdit(find="old text", replace="new text")
            ],
            task_implementation_plan_edits=[
                DocumentEdit(find="TODO", replace="Implement feature X")
            ]
        )

        assert response.message == "Task specification updated successfully."
        assert len(response.task_specification_edits) == 1
        assert len(response.task_implementation_plan_edits) == 1
        assert response.task_specification_edits[0].find == "old text"
        assert response.task_implementation_plan_edits[0].replace == "Implement feature X"

    def test_task_planning_response_optional_edits(self):
        """Test TaskPlanningResponse with optional edit fields."""
        response = TaskPlanningResponse(
            message="No changes needed at this time."
        )

        assert response.message == "No changes needed at this time."
        assert response.task_specification_edits is None
        assert response.task_implementation_plan_edits is None

    def test_task_planning_response_empty_edits(self):
        """Test TaskPlanningResponse with empty edit arrays."""
        response = TaskPlanningResponse(
            message="Review completed.",
            task_specification_edits=[],
            task_implementation_plan_edits=[]
        )

        assert response.message == "Review completed."
        assert response.task_specification_edits == []
        assert response.task_implementation_plan_edits == []


class TestDocumentEdit:
    """Test the simplified DocumentEdit schema."""

    def test_document_edit_creation(self):
        """Test creating DocumentEdit with simplified schema."""
        edit = DocumentEdit(find="old text", replace="new text")

        assert edit.find == "old text"
        assert edit.replace == "new text"

    def test_document_edit_validation(self):
        """Test DocumentEdit validation."""
        # Valid edit
        edit = DocumentEdit(find="find", replace="replace")
        assert edit.find == "find"
        assert edit.replace == "replace"

        # Empty strings should be allowed (for clearing content)
        empty_replace = DocumentEdit(find="text", replace="")
        assert empty_replace.replace == ""

    def test_document_edit_serialization(self):
        """Test DocumentEdit serialization to dict."""
        edit = DocumentEdit(find="old", replace="new")
        edit_dict = edit.model_dump()

        expected = {"find": "old", "replace": "new"}
        assert edit_dict == expected


class TestTaskPlanningAgentService:
    """Test the Task Planning Agent service with updated architecture."""

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        service = Mock()
        service.get_project_context = AsyncMock()
        return service

    @pytest.fixture
    def agent_service(self, mock_context_service):
        """Create agent service with mocked dependencies."""
        with patch('devboard.services.task_planning_agent.llm_service') as mock_llm_service:
            mock_llm_service.get_preferred_model_for_agent.return_value = "openai:gpt-4o"
            return TaskPlanningAgentService(context_service=mock_context_service)

    @pytest.fixture
    def sample_context_data(self):
        """Sample project context data."""
        return ProjectContextData(
            eager_context=[
                EagerContextData(
                    provider_type="github",
                    uri="https://github.com/org/repo",
                    description="Main repository",
                    data={"content": "Repository content..."}
                )
            ],
            on_demand_resources=[
                OnDemandResourceInfo(
                    provider_type="jira",
                    uri="https://jira.company.com/PROJECT-123",
                    description="Related Jira ticket",
                    has_user_description=True
                )
            ],
            provider_errors=[]
        )

    def test_task_state_enum(self):
        """Test TaskState enum values."""
        assert TaskState.DESIGNING == "Designing"
        assert TaskState.PLANNING == "Planning"

    def test_document_type_enum(self):
        """Test DocumentType enum values."""
        assert DocumentType.SPECIFICATION == "specification"
        assert DocumentType.IMPLEMENTATION_PLAN == "implementation_plan"

    def test_task_context_creation(self, sample_context_data):
        """Test TaskContext creation."""
        context = TaskContext(
            task_id=1,
            task_title="Test Task",
            task_description="Description",
            task_implementation_plan="Plan",
            task_state=TaskState.DESIGNING,
            project_id=100,
            eager_context=sample_context_data.eager_context,
            on_demand_resources=sample_context_data.on_demand_resources
        )

        assert context.task_id == 1
        assert context.task_title == "Test Task"
        assert context.task_state == TaskState.DESIGNING
        assert len(context.eager_context) == 1
        assert len(context.on_demand_resources) == 1

    def test_agent_creation_with_llm_service(self, agent_service):
        """Test that agents are created with LLMService model selection."""

        # Access the agents to trigger creation
        agents = agent_service.agents

        # Verify agents were created for each task state
        assert len(agents) == len(TaskState)

    @patch('devboard.services.task_planning_agent.llm_service')
    @pytest.mark.asyncio
    async def test_process_message_with_template_initialization(
        self, mock_llm_service, agent_service, mock_context_service, sample_context_data
    ):
        """Test message processing with template initialization."""
        mock_llm_service.get_preferred_model_for_agent.return_value = "openai:gpt-4o"
        mock_context_service.get_project_context.return_value = sample_context_data

        # Mock the agent run result
        mock_response = TaskPlanningResponse(
            message="Template initialized with task details.",
            task_specification_edits=[
                DocumentEdit(find="[Title]", replace="Test Task")
            ]
        )

        # Mock the agent run method
        with patch.object(agent_service.agents[TaskState.DESIGNING], 'run', new_callable=AsyncMock) as mock_run:
            mock_result = Mock()
            mock_result.output = mock_response
            mock_run.return_value = mock_result

            result = await agent_service.process_message(
                task_id=1,
                task_title="Test Task",
                task_description=None,  # Should trigger template initialization
                task_implementation_plan=None,
                task_state="Designing",
                project_id=100,
                user_message="Please help me create a task specification."
            )

            assert result.message == "Template initialized with task details."
            assert result.task_specification_edits is not None
            assert len(result.task_specification_edits) == 1
            mock_run.assert_called_once()

    @patch('devboard.services.task_planning_agent.llm_service')
    @pytest.mark.asyncio
    async def test_process_message_different_states(
        self, mock_llm_service, agent_service, mock_context_service, sample_context_data
    ):
        """Test that different task states use different agents."""
        mock_llm_service.get_preferred_model_for_agent.return_value = "openai:gpt-4o"
        mock_context_service.get_project_context.return_value = sample_context_data

        mock_response = TaskPlanningResponse(message="State-specific response")
        mock_result = Mock()
        mock_result.output = mock_response

        # Test Designing state
        with patch.object(agent_service.agents[TaskState.DESIGNING], 'run', new_callable=AsyncMock) as mock_designing_run:
            mock_designing_run.return_value = mock_result

            await agent_service.process_message(
                task_id=1, task_title="Test", task_description="desc",
                task_implementation_plan=None, task_state="Designing",
                project_id=100, user_message="test"
            )

            mock_designing_run.assert_called_once()

        # Test Planning state
        with patch.object(agent_service.agents[TaskState.PLANNING], 'run', new_callable=AsyncMock) as mock_planning_run:
            mock_planning_run.return_value = mock_result

            await agent_service.process_message(
                task_id=1, task_title="Test", task_description="desc",
                task_implementation_plan="plan", task_state="Planning",
                project_id=100, user_message="test"
            )

            mock_planning_run.assert_called_once()

    @patch('devboard.services.task_planning_agent.llm_service')
    def test_build_context_summary(self, mock_llm_service, agent_service, sample_context_data):
        """Test context summary building."""
        mock_llm_service.get_preferred_model_for_agent.return_value = "openai:gpt-4o"

        summary = agent_service._build_context_summary(sample_context_data)

        assert "EAGER CONTEXT (pre-loaded):" in summary
        assert "ON_DEMAND RESOURCES (use get_relevant_context tool):" in summary
        assert "github" in summary
        assert "jira" in summary
        assert "Main repository" in summary
        assert "Related Jira ticket" in summary

    @patch('devboard.services.task_planning_agent.llm_service')
    def test_build_documents_info_designing_state(self, mock_llm_service, agent_service):
        """Test document info building for Designing state."""
        mock_llm_service.get_preferred_model_for_agent.return_value = "openai:gpt-4o"

        info = agent_service._build_documents_info(
            description="Current task description",
            implementation_plan=None,
            state=TaskState.DESIGNING
        )

        assert "TASK SPECIFICATION (editable):" in info
        assert "Current task description" in info
        assert "IMPLEMENTATION PLAN" not in info

    @patch('devboard.services.task_planning_agent.llm_service')
    def test_build_documents_info_planning_state(self, mock_llm_service, agent_service):
        """Test document info building for Planning state."""
        mock_llm_service.get_preferred_model_for_agent.return_value = "openai:gpt-4o"

        info = agent_service._build_documents_info(
            description="Task description",
            implementation_plan="Implementation plan",
            state=TaskState.PLANNING
        )

        assert "TASK SPECIFICATION (editable):" in info
        assert "IMPLEMENTATION PLAN (editable):" in info
        assert "Task description" in info
        assert "Implementation plan" in info

    @patch('devboard.services.task_planning_agent.llm_service')
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_llm_service, agent_service, mock_context_service):
        """Test error handling in message processing."""
        mock_llm_service.get_preferred_model_for_agent.return_value = "openai:gpt-4o"
        mock_context_service.get_project_context.side_effect = Exception("Context error")

        result = await agent_service.process_message(
            task_id=1, task_title="Test", task_description="desc",
            task_implementation_plan=None, task_state="Designing",
            project_id=100, user_message="test"
        )

        assert "I encountered an error processing your message" in result.message
        assert "Context error" in result.message

    @patch('devboard.services.task_planning_agent.llm_service')
    @patch('devboard.services.task_planning_agent.template_service')
    @pytest.mark.asyncio
    async def test_template_service_integration(
        self, mock_template_service, mock_llm_service, agent_service, mock_context_service, sample_context_data
    ):
        """Test integration with template service."""
        mock_llm_service.get_preferred_model_for_agent.return_value = "openai:gpt-4o"
        mock_context_service.get_project_context.return_value = sample_context_data
        mock_template_service.get_task_specification_template.return_value = "# Task Specification: [Title]\n\nTemplate content"

        mock_response = TaskPlanningResponse(message="Template applied")
        mock_result = Mock()
        mock_result.output = mock_response

        with patch.object(agent_service.agents[TaskState.DESIGNING], 'run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            await agent_service.process_message(
                task_id=1,
                task_title="Test Task",
                task_description=None,  # Should trigger template
                task_implementation_plan=None,
                task_state="Designing",
                project_id=100,
                user_message="Initialize spec"
            )

            # Verify template service was called
            mock_template_service.get_task_specification_template.assert_called_once()
