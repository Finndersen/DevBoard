"""Tests for Task Role classes with deferred tools."""

from unittest.mock import Mock

import pytest
from pydantic_ai.exceptions import ModelRetry

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.task_planning import TaskPlanningRole
from devboard.agents.roles.task_specification import TaskSpecificationRole
from devboard.agents.tools import create_document_edit_tool, create_set_document_content_tool
from devboard.api.schemas import DocumentEdit
from devboard.db.models import Document
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import DocumentRepository
from tests.conftest import create_mock_task


class TestTaskSpecificationRole:
    """Test the TaskSpecificationRole for the Designing state."""

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
    def mock_agent_config_service(self):
        """Create a mock agent config service."""
        return Mock(spec=AgentConfigService)

    @pytest.fixture
    def role(self, mock_task, mock_document_repo, mock_agent_config_service):
        """Create TaskSpecificationRole instance."""
        return TaskSpecificationRole(
            task=mock_task,
            document_repository=mock_document_repo,
            agent_config_service=mock_agent_config_service,
        )

    def test_role_initialization(self, role, mock_task):
        """Test role initializes with correct task and document."""
        assert role.task == mock_task
        assert role.document_repository is not None

    def test_system_prompt(self, role):
        """Test role has appropriate system prompt."""
        prompt = role.get_system_prompt()
        assert "Task Specification Assistant" in prompt
        assert "task specification" in prompt.lower()

    def test_get_tools(self, role, mock_task):
        """Test role creates correct tools for specification."""
        tools = role.get_tools()

        # Should have set_content, edit tools for specification, and codebase investigation tool
        assert len(tools) == 3
        tool_names = [tool.name for tool in tools]

        # Should have set_content, edit, and codebase investigation tools
        assert f"set_{DocumentType.TASK_SPECIFICATION}_content" in tool_names
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert "investigate_codebase" in tool_names

    @pytest.mark.asyncio
    async def test_context_content(self, role, mock_task):
        """Test context content includes specification."""
        content = await role.get_context_content()

        assert "TASK SPECIFICATION DOCUMENT" in content
        assert mock_task.specification.content in content
        assert "IMPLEMENTATION PLAN" not in content  # Should not include plan in specification role


class TestTaskPlanningRole:
    """Test the TaskPlanningRole for the Planning state."""

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
    def mock_agent_config_service(self):
        """Create a mock agent config service."""
        return Mock(spec=AgentConfigService)

    @pytest.fixture
    def role(self, mock_task, mock_document_repo, mock_agent_config_service):
        """Create TaskPlanningRole instance."""
        return TaskPlanningRole(
            task=mock_task,
            document_repository=mock_document_repo,
            agent_config_service=mock_agent_config_service,
        )

    def test_role_initialization(self, role, mock_task):
        """Test role initializes with correct task."""
        assert role.task == mock_task

    def test_system_prompt(self, role):
        """Test role has appropriate system prompt for planning."""
        prompt = role.get_system_prompt()
        assert "Task Planning Assistant" in prompt
        assert "Implementation Plan" in prompt
        assert "implementation plan" in prompt.lower()

    def test_get_tools(self, role, mock_task):
        """Test role creates tools for both documents in planning."""
        tools = role.get_tools()

        # Should have set_content for implementation plan, edit tools for both documents, and codebase investigation tool
        assert len(tools) == 4

        tool_names = [tool.name for tool in tools]
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" in tool_names
        assert f"edit_{DocumentType.TASK_IMPLEMENTATION_PLAN}" in tool_names
        assert "investigate_codebase" in tool_names

    @pytest.mark.asyncio
    async def test_context_content(self, role, mock_task):
        """Test context content includes both documents."""
        content = await role.get_context_content()

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
        """Test document edit tool is created correctly with proper metadata."""
        tool = create_document_edit_tool(mock_document, mock_document_repo)

        # Verify tool name
        assert tool.name == f"edit_{mock_document.document_type}"

        # Verify tool description
        assert "Apply edits to the virtual document." in tool.description
        assert "DOCUMENT EDITING RULES" in tool.description

        # Verify tool requires approval
        assert tool.requires_approval is True

        # Verify argument schema has expected fields
        json_schema = tool.function_schema.json_schema
        properties = json_schema["properties"]
        assert properties["edits"]["description"] == "List of find-replace edits to apply"
        assert properties["reasoning"]["description"] == "Optional CONCISE reasoning for why these edits are being made"

        # Verify edits field is an array
        assert properties["edits"]["type"] == "array"

    def test_tool_pre_validation_failure(self, mock_document, mock_document_repo):
        """Test tool returns error for invalid edits."""
        tool = create_document_edit_tool(mock_document, mock_document_repo)

        # Invalid edit (text not found)
        edits = [DocumentEdit(old_string="NonExistent", new_string="Modified")]

        # Should raise ModelRetry for invalid edits
        with pytest.raises(ModelRetry, match="Failed to apply edits"):
            tool.function(edits, "Test edit")

    def test_tool_applies_valid_edits(self, mock_document, mock_document_repo):
        """Test tool validates and applies valid edits successfully."""
        tool = create_document_edit_tool(mock_document, mock_document_repo)

        edits = [DocumentEdit(old_string="Original", new_string="Modified")]

        # Tool function should execute successfully for valid edits
        result = tool.function(edits, "Test edit")

        assert "successfully" in result
        # Verify repository update was called
        mock_document_repo.update_content.assert_called_once()
        # Check the new content
        args = mock_document_repo.update_content.call_args[0]
        assert args[0] == mock_document
        assert "Modified content" == args[1]

    def test_tool_creation_without_approval(self, mock_document, mock_document_repo):
        """Test document edit tool can be created without approval requirement."""
        tool = create_document_edit_tool(mock_document, mock_document_repo, requires_approval=False)

        # Verify tool name
        assert tool.name == f"edit_{mock_document.document_type}"

        # Verify tool does NOT require approval when explicitly set to False
        assert tool.requires_approval is False

    def test_tool_creation_with_explicit_approval(self, mock_document, mock_document_repo):
        """Test document edit tool respects explicit approval requirement."""
        tool = create_document_edit_tool(mock_document, mock_document_repo, requires_approval=True)

        # Verify tool requires approval when explicitly set to True
        assert tool.requires_approval is True


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

    def test_tool_rejects_empty_content(self, mock_blank_document, mock_document_repo):
        """Test tool rejects empty or whitespace-only content."""
        tool = create_set_document_content_tool(mock_blank_document, mock_document_repo)

        # Empty content should raise ModelRetry
        from pydantic_ai.exceptions import ModelRetry

        with pytest.raises(ModelRetry, match="Content cannot be empty"):
            tool.function("")

        # Whitespace-only content should also raise ModelRetry
        with pytest.raises(ModelRetry, match="Content cannot be empty"):
            tool.function("   \n  ")

    def test_tool_sets_content_directly_for_blank_document(self, mock_blank_document, mock_document_repo):
        """Test tool sets content directly without requiring approval for blank documents."""
        tool = create_set_document_content_tool(mock_blank_document, mock_document_repo)

        # Verify tool does NOT require approval for blank documents (non-destructive)
        assert tool.requires_approval is False

        new_content = "# New Document\n\nThis is the initial content."
        result = tool.function(new_content)

        assert "successfully" in result
        # Verify repository update was called
        mock_document_repo.update_content.assert_called_once()
        # Check the arguments
        args = mock_document_repo.update_content.call_args[0]
        assert args[0] == mock_blank_document
        assert args[1] == new_content

    def test_tool_requires_approval_for_document_with_content(self, mock_document_with_content, mock_document_repo):
        """Test tool requires approval when setting content on document that already has content."""
        tool = create_set_document_content_tool(mock_document_with_content, mock_document_repo)

        # Verify tool requires approval for documents with existing content (framework handles this)
        assert tool.requires_approval is True

        # Tool function should execute successfully when called
        result = tool.function("New content replacing existing")
        assert "successfully" in result

    def test_tool_sets_content_when_approved_for_document_with_content(
        self, mock_document_with_content, mock_document_repo
    ):
        """Test tool sets content for document with existing content (approval handled by framework)."""
        tool = create_set_document_content_tool(mock_document_with_content, mock_document_repo)

        # Verify tool requires approval
        assert tool.requires_approval is True

        new_content = "# Replaced Document\n\nThis replaces the existing content."
        result = tool.function(new_content)

        assert "successfully" in result
        # Verify repository update was called
        mock_document_repo.update_content.assert_called_once()
        # Check the arguments
        args = mock_document_repo.update_content.call_args[0]
        assert args[0] == mock_document_with_content
        assert args[1] == new_content

    def test_tool_override_approval_for_blank_document(self, mock_blank_document, mock_document_repo):
        """Test tool can require approval for blank document when explicitly set."""
        tool = create_set_document_content_tool(mock_blank_document, mock_document_repo, requires_approval=True)

        # Verify tool requires approval even for blank document when explicitly set
        assert tool.requires_approval is True

    def test_tool_override_approval_for_document_with_content(self, mock_document_with_content, mock_document_repo):
        """Test tool can skip approval for document with content when explicitly set."""
        tool = create_set_document_content_tool(mock_document_with_content, mock_document_repo, requires_approval=False)

        # Verify tool does not require approval when explicitly set to False
        assert tool.requires_approval is False

    def test_tool_smart_approval_logic_with_none(
        self, mock_blank_document, mock_document_with_content, mock_document_repo
    ):
        """Test tool uses smart approval logic when requires_approval is None (default)."""
        # Blank document should not require approval
        tool_blank = create_set_document_content_tool(mock_blank_document, mock_document_repo, requires_approval=None)
        assert tool_blank.requires_approval is False

        # Document with content should require approval
        tool_with_content = create_set_document_content_tool(
            mock_document_with_content, mock_document_repo, requires_approval=None
        )
        assert tool_with_content.requires_approval is True


class TestRoleToolSelection:
    """Test that roles select the correct tools based on document state."""

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
    def mock_agent_config_service(self):
        """Create a mock agent config service."""
        return Mock(spec=AgentConfigService)

    def test_specification_role_providesonly_set_content_for_empty(
        self, mock_task_with_blank_spec, mock_document_repo, mock_agent_config_service
    ):
        """Test TaskSpecificationRole provides set_content and investigation tool for empty documents."""
        role = TaskSpecificationRole(
            task=mock_task_with_blank_spec,
            document_repository=mock_document_repo,
            agent_config_service=mock_agent_config_service,
        )

        tools = role.get_tools()
        assert len(tools) == 2
        tool_names = [tool.name for tool in tools]
        assert f"set_{DocumentType.TASK_SPECIFICATION}_content" in tool_names
        assert "investigate_codebase" in tool_names

    def test_specification_role_provides_both_tools_for_document_with_content(
        self, mock_task_with_content, mock_document_repo, mock_agent_config_service
    ):
        """Test TaskSpecificationRole provides document tools and investigation tool when document has content."""
        role = TaskSpecificationRole(
            task=mock_task_with_content,
            document_repository=mock_document_repo,
            agent_config_service=mock_agent_config_service,
        )

        tools = role.get_tools()
        assert len(tools) == 3
        tool_names = [tool.name for tool in tools]
        assert f"set_{DocumentType.TASK_SPECIFICATION}_content" in tool_names
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert "investigate_codebase" in tool_names

    def test_planning_role_provides_only_set_content_for_empty_plan(
        self, mock_task_with_blank_spec, mock_document_repo
    ):
        """Test TaskPlanningRole provides set_content for plan, edit for specification, and investigation tool."""
        role = TaskPlanningRole(
            task=mock_task_with_blank_spec,
            document_repository=mock_document_repo,
        )

        tools = role.get_tools()
        assert len(tools) == 3  # set_content for plan, edit for specification, and investigation tool
        tool_names = [tool.name for tool in tools]
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" in tool_names
        assert "investigate_codebase" in tool_names

    def test_planning_role_provides_set_and_edit_for_plan_with_content(
        self, mock_task_with_content, mock_document_repo
    ):
        """Test TaskPlanningRole provides all tools when documents have content."""
        role = TaskPlanningRole(
            task=mock_task_with_content,
            document_repository=mock_document_repo,
        )

        tools = role.get_tools()
        assert len(tools) == 4  # set_content + edit for plan, edit for specification, investigation tool
        tool_names = [tool.name for tool in tools]
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" in tool_names
        assert f"edit_{DocumentType.TASK_IMPLEMENTATION_PLAN}" in tool_names
        assert "investigate_codebase" in tool_names


class TestDocumentEdit:
    """Test the DocumentEdit schema."""

    def test_document_edit_creation(self):
        """Test creating DocumentEdit objects."""
        edit = DocumentEdit(old_string="old text", new_string="new text")

        assert edit.old_string == "old text"
        assert edit.new_string == "new text"

    def test_document_edit_serialization(self):
        """Test DocumentEdit serialization."""
        edit = DocumentEdit(old_string="find this", new_string="replace with this")

        data = edit.model_dump()
        assert data == {"old_string": "find this", "new_string": "replace with this"}

    def test_document_edit_empty_replace(self):
        """Test DocumentEdit allows empty replacement (deletion)."""
        edit = DocumentEdit(old_string="remove this", new_string="")

        assert edit.old_string == "remove this"
        assert edit.new_string == ""
