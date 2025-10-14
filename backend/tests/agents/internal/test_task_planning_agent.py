"""Tests for Task Planning Agents with deferred tools."""

from unittest.mock import MagicMock, Mock

import pytest
from pydantic_ai import ApprovalRequired

from devboard.agents.engines.internal import BaseDeps, TaskPlanningAgent, TaskSpecificationAgent
from devboard.agents.engines.internal.tools import create_document_edit_tool, create_set_document_content_tool
from devboard.api.schemas import DocumentEdit
from devboard.db.models import Document
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import DocumentRepository
from tests.conftest import create_mock_task


class TestTaskSpecificationAgent:
    """Test the TaskSpecificationAgent for the Designing state."""

    @pytest.fixture
    def mock_task(self):
        """Create a mock task with specification document."""
        return create_mock_task(
            task_id=1,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification_content="# Task Specification\n\nInitial content",
            implementation_plan_content="# Implementation Plan\n\nEmpty",
        )

    @pytest.fixture
    def mock_document_repo(self):
        """Create a mock document repository."""
        repo = Mock(spec=DocumentRepository)
        repo.update_content = Mock()
        return repo

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        return Mock()

    @pytest.fixture
    def agent(self, mock_task, mock_document_repo, mock_context_service):
        """Create TaskSpecificationAgent instance."""
        return TaskSpecificationAgent(
            context_service=mock_context_service,
            model_name="openai:gpt-4",
            task=mock_task,
            document_repository=mock_document_repo,
        )

    def test_agent_initialization(self, agent, mock_task):
        """Test agent initializes with correct task and document."""
        assert agent.task == mock_task
        assert agent.agent_role.value == "task_specification"

    def test_system_prompt(self, agent):
        """Test agent has appropriate system prompt."""
        prompt = agent._get_system_prompt()
        assert "Task Specification Assistant" in prompt
        assert "task specification" in prompt.lower()

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

        assert "TASK SPECIFICATION DOCUMENT" in content
        assert mock_task.specification.content in content
        assert "IMPLEMENTATION PLAN" not in content  # Should not include plan in Designing state


class TestTaskPlanningAgent:
    """Test the TaskPlanningAgent for the Planning state."""

    @pytest.fixture
    def mock_task(self):
        """Create a mock task with both documents."""
        return create_mock_task(
            task_id=2,
            title="Planning Task",
            status=TaskStatus.PLANNING,
            specification_content="# Task Specification\n\nDetailed spec",
            implementation_plan_content="# Implementation Plan\n\nPlan content",
        )

    @pytest.fixture
    def mock_document_repo(self):
        """Create a mock document repository."""
        repo = Mock(spec=DocumentRepository)
        repo.update_content = Mock()
        return repo

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        return Mock()

    @pytest.fixture
    def agent(self, mock_task, mock_document_repo, mock_context_service):
        """Create TaskPlanningAgent instance."""
        return TaskPlanningAgent(
            context_service=mock_context_service,
            model_name="openai:gpt-4",
            task=mock_task,
            document_repository=mock_document_repo,
        )

    def test_agent_initialization(self, agent, mock_task):
        """Test agent initializes with correct task."""
        assert agent.task == mock_task
        assert agent.agent_role.value == "task_planning"

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
        tool = create_document_edit_tool(mock_document, mock_document_repo)

        assert tool.name == f"edit_{mock_document.document_type}"

    def test_tool_pre_validation_success(self, mock_document, mock_document_repo):
        """Test tool validates edits before approval."""
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


class TestSetDocumentContentTool:
    """Test the document content setting tool creation and behavior."""

    @pytest.fixture
    def mock_blank_document(self):
        """Create a mock blank document."""
        doc = Mock(spec=Document)
        doc.id = 200
        doc.document_type = DocumentType.TASK_SPECIFICATION
        doc.content = ""
        return doc

    @pytest.fixture
    def mock_document_with_content(self):
        """Create a mock document with existing content."""
        doc = Mock(spec=Document)
        doc.id = 201
        doc.document_type = DocumentType.TASK_SPECIFICATION
        doc.content = "Existing content"
        return doc

    @pytest.fixture
    def mock_document_repo(self):
        """Create a mock document repository."""
        repo = Mock(spec=DocumentRepository)
        repo.update_content = Mock()
        return repo

    def test_tool_creation(self, mock_blank_document, mock_document_repo):
        """Test set document content tool is created correctly."""
        tool = create_set_document_content_tool(mock_blank_document, mock_document_repo)

        assert tool.name == f"set_{mock_blank_document.document_type}_content"

    def test_tool_requires_approval_for_valid_content(self, mock_blank_document, mock_document_repo):
        """Test tool requests approval for valid content on blank document."""
        tool = create_set_document_content_tool(mock_blank_document, mock_document_repo)

        ctx = MagicMock()
        ctx.tool_call_approved = False

        # Tool should raise ApprovalRequired for valid content
        with pytest.raises(ApprovalRequired):
            tool.function(ctx, "New content for blank document")

    def test_tool_rejects_empty_content(self, mock_blank_document, mock_document_repo):
        """Test tool rejects empty or whitespace-only content."""
        tool = create_set_document_content_tool(mock_blank_document, mock_document_repo)

        ctx = MagicMock()
        ctx.tool_call_approved = False

        # Empty content should return error
        result = tool.function(ctx, "")
        assert "Error: Content cannot be empty" in result

        # Whitespace-only content should also return error
        result = tool.function(ctx, "   \n  ")
        assert "Error: Content cannot be empty" in result

    def test_tool_rejects_non_blank_document(self, mock_document_with_content, mock_document_repo):
        """Test tool rejects setting content on document that already has content."""
        tool = create_set_document_content_tool(mock_document_with_content, mock_document_repo)

        ctx = MagicMock()
        ctx.tool_call_approved = False

        result = tool.function(ctx, "New content")
        assert "Error: Document already has content" in result
        assert f"edit_{mock_document_with_content.document_type}" in result

    def test_tool_applies_approved_content(self, mock_blank_document, mock_document_repo):
        """Test tool sets content when approved."""
        tool = create_set_document_content_tool(mock_blank_document, mock_document_repo)

        ctx = MagicMock()
        ctx.tool_call_approved = True

        new_content = "# New Document\n\nThis is the initial content."
        result = tool.function(ctx, new_content)

        assert "successfully" in result
        # Verify repository update was called
        mock_document_repo.update_content.assert_called_once()
        # Check the arguments
        args = mock_document_repo.update_content.call_args[0]
        assert args[0] == mock_blank_document
        assert args[1] == new_content


class TestAgentToolSelection:
    """Test that agents select the correct tool based on document state."""

    @pytest.fixture
    def mock_task_with_blank_spec(self):
        """Create a mock task with blank specification."""
        return create_mock_task(
            task_id=300,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification_content="",
            implementation_plan_content="",
        )

    @pytest.fixture
    def mock_task_with_content(self):
        """Create a mock task with content in both documents."""
        return create_mock_task(
            task_id=400,
            title="Planning Task",
            status=TaskStatus.PLANNING,
            specification_content="# Specification\n\nContent here",
            implementation_plan_content="# Plan\n\nPlan content",
        )

    @pytest.fixture
    def mock_document_repo(self):
        """Create a mock document repository."""
        return Mock(spec=DocumentRepository)

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        return Mock()

    def test_specification_agent_uses_set_tool_for_blank_document(
        self, mock_task_with_blank_spec, mock_document_repo, mock_context_service
    ):
        """Test TaskSpecificationAgent uses set_content tool when document is blank."""
        agent = TaskSpecificationAgent(
            context_service=mock_context_service,
            model_name="openai:gpt-4",
            task=mock_task_with_blank_spec,
            document_repository=mock_document_repo,
        )

        tools = agent._get_tools()
        assert len(tools) == 1
        assert tools[0].name == f"set_{DocumentType.TASK_SPECIFICATION}_content"

    def test_specification_agent_uses_edit_tool_for_document_with_content(
        self, mock_task_with_content, mock_document_repo, mock_context_service
    ):
        """Test TaskSpecificationAgent uses edit tool when document has content."""
        agent = TaskSpecificationAgent(
            context_service=mock_context_service,
            model_name="openai:gpt-4",
            task=mock_task_with_content,
            document_repository=mock_document_repo,
        )

        tools = agent._get_tools()
        assert len(tools) == 1
        assert tools[0].name == f"edit_{DocumentType.TASK_SPECIFICATION}"

    def test_planning_agent_uses_appropriate_tools_for_both_documents(
        self, mock_task_with_blank_spec, mock_document_repo, mock_context_service
    ):
        """Test TaskPlanningAgent uses appropriate tools based on each document's state."""
        # Modify task to have blank spec and blank plan
        agent = TaskPlanningAgent(
            context_service=mock_context_service,
            model_name="openai:gpt-4",
            task=mock_task_with_blank_spec,
            document_repository=mock_document_repo,
        )

        tools = agent._get_tools()
        assert len(tools) == 2
        tool_names = [tool.name for tool in tools]
        assert f"set_{DocumentType.TASK_SPECIFICATION}_content" in tool_names
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" in tool_names

    def test_planning_agent_mixed_document_states(
        self, mock_task_with_blank_spec, mock_document_repo, mock_context_service
    ):
        """Test TaskPlanningAgent handles mixed document states correctly."""
        # Set spec to have content, but plan to be blank
        mock_task_with_blank_spec.specification.content = "# Spec\n\nContent"

        agent = TaskPlanningAgent(
            context_service=mock_context_service,
            model_name="openai:gpt-4",
            task=mock_task_with_blank_spec,
            document_repository=mock_document_repo,
        )

        tools = agent._get_tools()
        assert len(tools) == 2
        tool_names = [tool.name for tool in tools]
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" in tool_names


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
