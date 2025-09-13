"""Tests for Task Planning Agents with deferred tools."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from pydantic_ai import ApprovalRequired

from devboard.agents.deps import BaseDeps
from devboard.agents.task_agent import (
    TaskPlanningAgent,
    TaskSpecificationAgent,
)
from devboard.api.schemas import DocumentEdit
from devboard.db.models import Document, Task
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import DocumentRepository


class TestTaskSpecificationAgent:
    """Test the TaskSpecificationAgent for the Designing state."""

    @pytest.fixture
    def mock_task(self):
        """Create a mock task with specification document."""
        task = Mock(spec=Task)
        task.id = 1
        task.name = "Test Task"
        task.status = TaskStatus.DEFINING

        # Mock specification document
        spec_doc = Mock(spec=Document)
        spec_doc.id = 10
        spec_doc.document_type = DocumentType.TASK_SPECIFICATION
        spec_doc.content = "# Task Specification\n\nInitial content"
        task.specification = spec_doc

        # Mock implementation plan document
        plan_doc = Mock(spec=Document)
        plan_doc.id = 11
        plan_doc.document_type = DocumentType.TASK_IMPLEMENTATION_PLAN
        plan_doc.content = "# Implementation Plan\n\nEmpty"
        task.implementation_plan = plan_doc

        return task

    @pytest.fixture
    def mock_document_repo(self):
        """Create a mock document repository."""
        repo = Mock(spec=DocumentRepository)
        repo.update_content = Mock()
        return repo

    @pytest.fixture
    def agent(self, mock_task, mock_document_repo):
        """Create TaskSpecificationAgent instance."""
        with (
            patch("devboard.agents.base_agent.llm_service") as mock_llm,
            patch("devboard.agents.base_agent.context_assembly_service") as mock_context,
        ):
            mock_llm.get_preferred_model_for_agent.return_value = "test"
            return TaskSpecificationAgent(task=mock_task, document_repository=mock_document_repo)

    def test_agent_initialization(self, agent, mock_task):
        """Test agent initializes with correct task and document."""
        assert agent.task == mock_task
        assert agent.agent_type.value == "task_specification"

    def test_system_prompt(self, agent):
        """Test agent has appropriate system prompt."""
        prompt = agent._get_system_prompt()
        assert "Task Specification Assistant" in prompt
        assert "Designing" in prompt
        assert "Edit the Task Specification document only" in prompt

    def test_get_tools(self, agent, mock_task):
        """Test agent creates correct tools for Designing state."""
        tools = agent._get_tools()

        # Should have one tool for editing specification
        assert len(tools) == 1
        tool = tools[0]

        # Tool should be for editing specification document
        assert tool.name == f"edit_{DocumentType.TASK_SPECIFICATION}"

    @pytest.mark.asyncio
    async def test_context_message_content(self, agent, mock_task):
        """Test context message includes specification content."""
        deps = BaseDeps()
        content = await agent._get_context_message_content(deps)

        assert "TASK SPECIFICATION DOCUMENT:" in content
        assert mock_task.specification.content in content
        assert "Implementation Plan" not in content  # Should not include plan in Designing state


class TestTaskPlanningAgent:
    """Test the TaskPlanningAgent for the Planning state."""

    @pytest.fixture
    def mock_task(self):
        """Create a mock task with both documents."""
        task = Mock(spec=Task)
        task.id = 2
        task.name = "Planning Task"
        task.status = TaskStatus.PLANNING

        # Mock specification document
        spec_doc = Mock(spec=Document)
        spec_doc.id = 20
        spec_doc.document_type = DocumentType.TASK_SPECIFICATION
        spec_doc.content = "# Task Specification\n\nDetailed spec"
        task.specification = spec_doc

        # Mock implementation plan document
        plan_doc = Mock(spec=Document)
        plan_doc.id = 21
        plan_doc.document_type = DocumentType.TASK_IMPLEMENTATION_PLAN
        plan_doc.content = "# Implementation Plan\n\nPlan content"
        task.implementation_plan = plan_doc

        return task

    @pytest.fixture
    def mock_document_repo(self):
        """Create a mock document repository."""
        repo = Mock(spec=DocumentRepository)
        repo.update_content = Mock()
        return repo

    @pytest.fixture
    def agent(self, mock_task, mock_document_repo):
        """Create TaskPlanningAgent instance."""
        with (
            patch("devboard.agents.base_agent.llm_service") as mock_llm,
            patch("devboard.agents.base_agent.context_assembly_service") as mock_context,
        ):
            mock_llm.get_preferred_model_for_agent.return_value = "test"
            return TaskPlanningAgent(task=mock_task, document_repository=mock_document_repo)

    def test_agent_initialization(self, agent, mock_task):
        """Test agent initializes with correct task."""
        assert agent.task == mock_task
        assert agent.agent_type.value == "task_planning"

    def test_system_prompt(self, agent):
        """Test agent has appropriate system prompt for Planning state."""
        prompt = agent._get_system_prompt()
        assert "Task Planning Assistant" in prompt
        assert "Planning" in prompt
        assert "Edit both Task Specification and Implementation Plan" in prompt

    def test_get_tools(self, agent, mock_task):
        """Test agent creates tools for both documents in Planning state."""
        tools = agent._get_tools()

        # Should have two tools for editing both documents
        assert len(tools) == 2

        tool_names = [tool.name for tool in tools]
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert f"edit_{DocumentType.TASK_IMPLEMENTATION_PLAN}" in tool_names

    @pytest.mark.asyncio
    async def test_context_message_content(self, agent, mock_task):
        """Test context message includes both documents."""
        deps = BaseDeps()
        content = await agent._get_context_message_content(deps)

        assert "TASK SPECIFICATION DOCUMENT:" in content
        assert mock_task.specification.content in content
        assert "TASK IMPLEMENTATION PLAN DOCUMENT:" in content
        assert mock_task.implementation_plan.content in content


class TestDocumentEditTool:
    """Test the document editing tool creation and behavior."""

    @pytest.fixture
    def mock_document(self):
        """Create a mock document."""
        doc = Mock(spec=Document)
        doc.id = 100
        doc.document_type = DocumentType.TASK_SPECIFICATION
        doc.content = "Original content"
        return doc

    @pytest.fixture
    def mock_document_repo(self):
        """Create a mock document repository."""
        repo = Mock(spec=DocumentRepository)
        repo.update_content = Mock()
        return repo

    def test_tool_creation(self, mock_document, mock_document_repo):
        """Test document edit tool is created correctly."""
        from devboard.agents.tools import create_document_edit_tool

        tool = create_document_edit_tool(mock_document, mock_document_repo)

        assert tool.name == f"edit_{mock_document.document_type}"
        assert tool.requires_approval == True

    def test_tool_pre_validation_success(self, mock_document, mock_document_repo):
        """Test tool validates edits before approval."""
        from devboard.agents.tools import create_document_edit_tool

        tool = create_document_edit_tool(mock_document, mock_document_repo)

        # Create a mock context
        ctx = MagicMock()
        ctx.tool_call_approved = False  # Not approved yet

        edits = [DocumentEdit(find="Original", replace="Modified")]

        # Tool should raise ApprovalRequired for valid edits
        with pytest.raises(ApprovalRequired):
            tool.function(ctx, edits, "Test edit")

    def test_tool_pre_validation_failure(self, mock_document, mock_document_repo):
        """Test tool returns error for invalid edits."""
        from devboard.agents.tools import create_document_edit_tool

        tool = create_document_edit_tool(mock_document, mock_document_repo)

        # Create a mock context
        ctx = MagicMock()
        ctx.tool_call_approved = False

        # Invalid edit (text not found)
        edits = [DocumentEdit(find="NonExistent", replace="Modified")]

        # Should return error message, not raise ApprovalRequired
        result = tool.function(ctx, edits, "Test edit")
        assert "Failed to apply edits" in result

    def test_tool_applies_approved_edits(self, mock_document, mock_document_repo):
        """Test tool applies edits when approved."""
        from devboard.agents.tools import create_document_edit_tool

        tool = create_document_edit_tool(mock_document, mock_document_repo)

        # Create a mock context with approval
        ctx = MagicMock()
        ctx.tool_call_approved = True  # Approved

        edits = [DocumentEdit(find="Original", replace="Modified")]

        # Should apply edits and update document
        result = tool.function(ctx, edits, "Test edit")

        assert "successfully" in result
        # Verify repository update was called
        mock_document_repo.update_content.assert_called_once()
        # Check the new content
        args = mock_document_repo.update_content.call_args[0]
        assert args[0] == mock_document
        assert "Modified content" == args[1]


class TestDocumentEdit:
    """Test the DocumentEdit schema."""

    def test_document_edit_creation(self):
        """Test creating DocumentEdit objects."""
        edit = DocumentEdit(find="old text", replace="new text")

        assert edit.find == "old text"
        assert edit.replace == "new text"

    def test_document_edit_serialization(self):
        """Test DocumentEdit serialization."""
        edit = DocumentEdit(find="find this", replace="replace with this")

        data = edit.model_dump()
        assert data == {"find": "find this", "replace": "replace with this"}

    def test_document_edit_empty_replace(self):
        """Test DocumentEdit allows empty replacement (deletion)."""
        edit = DocumentEdit(find="remove this", replace="")

        assert edit.find == "remove this"
        assert edit.replace == ""
