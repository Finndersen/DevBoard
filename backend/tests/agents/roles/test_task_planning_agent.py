"""Tests for Task Planning Role class with deferred tools."""

from unittest.mock import Mock

import pytest
from pydantic_ai.exceptions import ModelRetry

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.task_planning import TaskPlanningAgentRole
from devboard.agents.tools import create_document_edit_tool, create_set_document_content_tool
from devboard.api.schemas import DocumentEdit
from devboard.db.models import Document
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.task_service import TaskService
from tests.conftest import create_mock_task


class TestTaskPlanningRoleWithSpec:
    """Test the TaskPlanningRole when focused on specification (no implementation plan yet)."""

    @pytest.fixture
    def mock_task(self):
        """Create a mock task with specification document but no implementation plan."""
        return create_mock_task(
            task_id=1,
            title="Test Task",
            status=TaskStatus.PLANNING,
            specification_content="# Task Specification\n\nInitial content",
            implementation_plan_content=None,  # No plan yet
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
    def mock_task_service(self):
        """Create a mock task service."""
        service = Mock(spec=TaskService)
        service.get_custom_fields.return_value = []
        return service

    @pytest.fixture
    def role(self, mock_task, mock_document_repo, mock_agent_config_service, mock_task_service):
        """Create TaskPlanningRole instance."""
        return TaskPlanningAgentRole(
            task=mock_task,
            document_repository=mock_document_repo,
            agent_config_service=mock_agent_config_service,
            task_service=mock_task_service,
            conversation_repo=Mock(spec=ConversationRepository),
            conversation_id=None,
            working_dir="/test/working_dir",
        )

    def test_role_initialization(self, role, mock_task):
        """Test role initializes with correct task and document."""
        assert role.task == mock_task
        assert role.document_repository is not None

    def test_system_prompt(self, role):
        """Test role has appropriate system prompt."""
        prompt = role.get_system_prompt()
        assert "Task Planning Assistant" in prompt
        assert "task specification" in prompt.lower()
        assert "implementation plan" in prompt.lower()

    def test_get_tools_without_implementation_plan(self, role, mock_task):
        """Test role creates correct tools when no implementation plan exists (no plan_service)."""
        tools = role.get_tools()

        # Should have list_tasks, view_task_details, create_task, investigate_codebase (common),
        # plus edit_task (own task) and edit for spec (always included now)
        assert len(tools) == 6
        tool_names = [tool.name for tool in tools]

        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert "investigate_codebase" in tool_names
        assert "create_task" in tool_names
        assert "edit_task" in tool_names
        assert "list_tasks" in tool_names
        assert "view_task_details" in tool_names

        # Should NOT have plan tools (no plan_service provided)
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" not in tool_names
        assert f"edit_{DocumentType.TASK_IMPLEMENTATION_PLAN}" not in tool_names

    @pytest.mark.asyncio
    async def test_context_content_without_implementation_plan(self, role, mock_task):
        """Test context content includes specification but not plan when plan doesn't exist."""
        content = await role.get_context_content()

        assert "## Task Specification" in content
        assert mock_task.specification.content in content
        # Should NOT include implementation plan section when it doesn't exist
        assert "IMPLEMENTATION PLAN" not in content


class TestTaskPlanningRoleWithPlan:
    """Test the TaskPlanningRole when implementation plan exists."""

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
    def mock_task_service(self):
        """Create a mock task service."""
        service = Mock(spec=TaskService)
        service.get_custom_fields.return_value = []
        return service

    @pytest.fixture
    def role(self, mock_task, mock_document_repo, mock_agent_config_service, mock_task_service):
        """Create TaskPlanningRole instance."""
        return TaskPlanningAgentRole(
            task=mock_task,
            document_repository=mock_document_repo,
            agent_config_service=mock_agent_config_service,
            task_service=mock_task_service,
            conversation_repo=Mock(spec=ConversationRepository),
            conversation_id=None,
            working_dir="/test/working_dir",
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

    def test_get_tools_with_implementation_plan(self, role, mock_task):
        """Test role creates tools for both documents in planning (doc-based plan, no plan_service)."""
        tools = role.get_tools()

        # Should have: list_tasks, view_task_details, create_task, investigate_codebase (common),
        # plus edit_task (own task), edit for spec (always), set_content for plan, edit for plan
        assert len(tools) == 8

        tool_names = [tool.name for tool in tools]
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" in tool_names
        assert f"edit_{DocumentType.TASK_IMPLEMENTATION_PLAN}" in tool_names
        assert "investigate_codebase" in tool_names
        assert "create_task" in tool_names
        assert "edit_task" in tool_names
        assert "list_tasks" in tool_names
        assert "view_task_details" in tool_names

    @pytest.mark.asyncio
    async def test_context_content_excludes_implementation_plan(self, role, mock_task):
        """Test context content excludes implementation plan (not needed at planning time)."""
        content = await role.get_context_content()

        assert "## Task Specification" in content
        assert mock_task.specification.content in content
        # Implementation plan is excluded from planning context snapshot
        assert "## Implementation Plan" not in content


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

        assert "successfully" in result.lower()
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

        assert "successfully" in result.lower()
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
        assert "successfully" in result.lower()

    def test_tool_sets_content_when_approved_for_document_with_content(
        self, mock_document_with_content, mock_document_repo
    ):
        """Test tool sets content for document with existing content (approval handled by framework)."""
        tool = create_set_document_content_tool(mock_document_with_content, mock_document_repo)

        # Verify tool requires approval
        assert tool.requires_approval is True

        new_content = "# Replaced Document\n\nThis replaces the existing content."
        result = tool.function(new_content)

        assert "successfully" in result.lower()
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
    def mock_task_with_blank_spec_and_plan(self):
        """Create a mock task with blank specification and plan."""
        return create_mock_task(
            task_id=300,
            title="Test Task",
            status=TaskStatus.PLANNING,
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
    def mock_task_with_spec_only(self):
        """Create a mock task with specification content but no plan yet."""
        return create_mock_task(
            task_id=500,
            title="Spec Only Task",
            status=TaskStatus.PLANNING,
            specification_content="# Specification\n\nContent here",
            implementation_plan_content=None,
        )

    @pytest.fixture
    def mock_document_repo(self):
        """Create a mock document repository."""
        return Mock(spec=DocumentRepository)

    @pytest.fixture
    def mock_agent_config_service(self):
        """Create a mock agent config service."""
        return Mock(spec=AgentConfigService)

    @pytest.fixture
    def mock_task_service(self):
        """Create a mock task service."""
        service = Mock(spec=TaskService)
        service.get_custom_fields.return_value = []
        return service

    def test_planning_role_provides_edit_spec_tool_even_for_empty_spec(
        self, mock_task_with_blank_spec_and_plan, mock_document_repo, mock_agent_config_service, mock_task_service
    ):
        """Test TaskPlanningRole always provides edit_specification tool (even when spec is empty)."""
        role = TaskPlanningAgentRole(
            task=mock_task_with_blank_spec_and_plan,
            document_repository=mock_document_repo,
            agent_config_service=mock_agent_config_service,
            task_service=mock_task_service,
            conversation_repo=Mock(spec=ConversationRepository),
            conversation_id=None,
            working_dir="/test/working_dir",
        )

        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        # edit_specification is now always included regardless of content
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" in tool_names
        assert "investigate_codebase" in tool_names
        assert "create_task" in tool_names
        assert "edit_task" in tool_names
        assert "list_tasks" in tool_names
        assert "view_task_details" in tool_names

        # edit plan NOT included because plan.content is empty (doc-based fallback path)
        assert f"edit_{DocumentType.TASK_IMPLEMENTATION_PLAN}" not in tool_names

    def test_planning_role_provides_both_tools_for_documents_with_content(
        self, mock_task_with_content, mock_document_repo, mock_agent_config_service, mock_task_service
    ):
        """Test TaskPlanningRole provides all tools when documents have content."""
        role = TaskPlanningAgentRole(
            task=mock_task_with_content,
            document_repository=mock_document_repo,
            agent_config_service=mock_agent_config_service,
            task_service=mock_task_service,
            conversation_repo=Mock(spec=ConversationRepository),
            conversation_id=None,
            working_dir="/test/working_dir",
        )

        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" in tool_names
        assert f"edit_{DocumentType.TASK_IMPLEMENTATION_PLAN}" in tool_names
        assert "investigate_codebase" in tool_names
        assert "create_task" in tool_names
        assert "edit_task" in tool_names
        assert "list_tasks" in tool_names
        assert "view_task_details" in tool_names

    def test_planning_role_provides_spec_tools_only_when_no_plan_exists(
        self, mock_task_with_spec_only, mock_document_repo, mock_agent_config_service, mock_task_service
    ):
        """Test TaskPlanningRole provides only spec tools when no implementation plan exists."""
        role = TaskPlanningAgentRole(
            task=mock_task_with_spec_only,
            document_repository=mock_document_repo,
            agent_config_service=mock_agent_config_service,
            task_service=mock_task_service,
            conversation_repo=Mock(spec=ConversationRepository),
            conversation_id=None,
            working_dir="/test/working_dir",
        )

        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        # Should have common tools plus edit_task (own) and edit for spec
        assert f"edit_{DocumentType.TASK_SPECIFICATION}" in tool_names
        assert "investigate_codebase" in tool_names
        assert "create_task" in tool_names
        assert "edit_task" in tool_names
        assert "list_tasks" in tool_names
        assert "view_task_details" in tool_names

        # Should NOT have plan tools (no plan exists yet)
        assert f"set_{DocumentType.TASK_IMPLEMENTATION_PLAN}_content" not in tool_names
        assert f"edit_{DocumentType.TASK_IMPLEMENTATION_PLAN}" not in tool_names


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
