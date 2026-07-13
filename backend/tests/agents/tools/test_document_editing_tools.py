"""Tests for document editing tools."""

from unittest.mock import Mock

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.document_editing import (
    build_project_context_document_tools,
    create_document_edit_tool,
    create_set_document_content_tool,
)
from devboard.api.schemas import DocumentEdit
from devboard.db.models import Document, Project, Task
from devboard.db.repositories import DocumentRepository
from devboard.services.system_event_emitter import SystemEventEmitter


@pytest.fixture
def mock_document():
    """Create a mock document."""
    doc = Mock(spec=Document)
    doc.id = 1
    doc.content = "Initial content\nwith multiple lines"
    doc.document_type = "task_specification"
    return doc


@pytest.fixture
def mock_task():
    """Create a mock task."""
    task = Mock(spec=Task)
    task.id = 42
    task.project_id = 10
    return task


@pytest.fixture
def mock_project():
    """Create a mock project."""
    project = Mock(spec=Project)
    project.id = 10
    return project


@pytest.fixture
def mock_document_repo():
    """Create a mock document repository."""
    repo = Mock(spec=DocumentRepository)
    repo.update_content = Mock()
    repo.commit = Mock()
    return repo


@pytest.fixture
def mock_system_event_emitter():
    """Create a mock system event emitter."""
    emitter = Mock(spec=SystemEventEmitter)
    emitter.emit_document_updated = Mock()
    return emitter


class TestCreateDocumentEditTool:
    """Tests for create_document_edit_tool factory and edit_document_tool inner function."""

    def test_edit_summary_is_required_parameter(self, mock_document, mock_task, mock_document_repo):
        """Verify that edit_summary is a required parameter (no default value)."""
        tool = create_document_edit_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
        )

        with pytest.raises(TypeError, match="missing 1 required positional argument: 'edit_summary'"):
            tool.function(
                edits=[
                    DocumentEdit(old_string="Initial", new_string="Modified"),
                ]
            )

    def test_successful_edit_emits_event(self, mock_document, mock_task, mock_document_repo, mock_system_event_emitter):
        """Successful edit with emitter emits document.updated event."""
        tool = create_document_edit_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
            system_event_emitter=mock_system_event_emitter,
        )

        result = tool.function(
            edits=[DocumentEdit(old_string="Initial", new_string="Modified")],
            edit_summary="Changed greeting",
        )

        mock_document_repo.update_content.assert_called_once()
        mock_document_repo.commit.assert_called_once()
        mock_system_event_emitter.emit_document_updated.assert_called_once_with(
            mock_task,
            "task_specification",
            "Changed greeting",
        )
        assert "Edits applied successfully" in result

    def test_successful_edit_with_project_parent_emits_event(
        self, mock_document, mock_project, mock_document_repo, mock_system_event_emitter
    ):
        """Successful edit with Project parent emits event to project."""
        tool = create_document_edit_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_project,
            system_event_emitter=mock_system_event_emitter,
        )

        tool.function(
            edits=[DocumentEdit(old_string="Initial", new_string="Modified")],
            edit_summary="Updated documentation",
        )

        mock_system_event_emitter.emit_document_updated.assert_called_once_with(
            mock_project,
            "task_specification",
            "Updated documentation",
        )

    def test_failed_edit_does_not_emit_event(
        self, mock_document, mock_task, mock_document_repo, mock_system_event_emitter
    ):
        """Failed edit (ModelRetry) does not emit event."""
        mock_document.content = None

        tool = create_document_edit_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
            system_event_emitter=mock_system_event_emitter,
        )

        with pytest.raises(ModelRetry):
            tool.function(
                edits=[DocumentEdit(old_string="Initial", new_string="Modified")],
                edit_summary="This should not emit",
            )

        mock_system_event_emitter.emit_document_updated.assert_not_called()
        mock_document_repo.update_content.assert_not_called()

    def test_no_event_emitted_when_emitter_is_none(self, mock_document, mock_task, mock_document_repo):
        """When system_event_emitter is None, no event is emitted (no error)."""
        tool = create_document_edit_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
            system_event_emitter=None,
        )

        result = tool.function(
            edits=[DocumentEdit(old_string="Initial", new_string="Modified")],
            edit_summary="Changed content",
        )

        mock_document_repo.update_content.assert_called_once()
        assert "Edits applied successfully" in result

    def test_tool_requires_approval_by_default(self, mock_document, mock_task, mock_document_repo):
        """Tool requires approval by default."""
        tool = create_document_edit_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
        )

        assert tool.requires_approval is True

    def test_tool_approval_can_be_disabled(self, mock_document, mock_task, mock_document_repo):
        """Tool approval requirement can be disabled."""
        tool = create_document_edit_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
            requires_approval=False,
        )

        assert tool.requires_approval is False


class TestCreateSetDocumentContentTool:
    """Tests for create_set_document_content_tool factory and set_document_content_tool inner function."""

    def test_edit_summary_is_required_parameter(self, mock_document, mock_task, mock_document_repo):
        """Verify that edit_summary is a required parameter (no default value)."""
        tool = create_set_document_content_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
        )

        with pytest.raises(TypeError, match="missing 1 required positional argument: 'edit_summary'"):
            tool.function(content="New content here")

    def test_successful_set_emits_event(self, mock_document, mock_task, mock_document_repo, mock_system_event_emitter):
        """Successful content set with emitter emits document.updated event."""
        tool = create_set_document_content_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
            system_event_emitter=mock_system_event_emitter,
        )

        result = tool.function(
            content="New specification content",
            edit_summary="Created initial specification",
        )

        mock_document_repo.update_content.assert_called_once_with(mock_document, "New specification content")
        mock_document_repo.commit.assert_called_once()
        mock_system_event_emitter.emit_document_updated.assert_called_once_with(
            mock_task,
            "task_specification",
            "Created initial specification",
        )
        assert "Successfully set content" in result

    def test_successful_set_with_project_parent_emits_event(
        self, mock_document, mock_project, mock_document_repo, mock_system_event_emitter
    ):
        """Successful content set with Project parent emits event to project."""
        tool = create_set_document_content_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_project,
            system_event_emitter=mock_system_event_emitter,
        )

        tool.function(
            content="Project documentation",
            edit_summary="Added project readme",
        )

        mock_system_event_emitter.emit_document_updated.assert_called_once_with(
            mock_project,
            "task_specification",
            "Added project readme",
        )

    def test_empty_content_raises_model_retry(
        self, mock_document, mock_task, mock_document_repo, mock_system_event_emitter
    ):
        """Empty content raises ModelRetry and does not emit event."""
        tool = create_set_document_content_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
            system_event_emitter=mock_system_event_emitter,
        )

        with pytest.raises(ModelRetry, match="Content cannot be empty"):
            tool.function(
                content="   ",
                edit_summary="This should not emit",
            )

        mock_system_event_emitter.emit_document_updated.assert_not_called()
        mock_document_repo.update_content.assert_not_called()

    def test_no_event_emitted_when_emitter_is_none(self, mock_document, mock_task, mock_document_repo):
        """When system_event_emitter is None, no event is emitted (no error)."""
        tool = create_set_document_content_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
            system_event_emitter=None,
        )

        result = tool.function(
            content="New content",
            edit_summary="Updated content",
        )

        mock_document_repo.update_content.assert_called_once()
        assert "Successfully set content" in result

    def test_smart_approval_logic_with_blank_document(self, mock_document, mock_task, mock_document_repo):
        """Tool does not require approval for blank documents by default."""
        mock_document.content = None

        tool = create_set_document_content_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
        )

        assert tool.requires_approval is False

    def test_smart_approval_logic_with_non_blank_document(self, mock_document, mock_task, mock_document_repo):
        """Tool requires approval for non-blank documents by default."""
        mock_document.content = "Existing content"

        tool = create_set_document_content_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
        )

        assert tool.requires_approval is True

    def test_explicit_approval_requirement_overrides_smart_logic(self, mock_document, mock_task, mock_document_repo):
        """Explicit requires_approval parameter overrides smart logic."""
        mock_document.content = "Existing content"

        tool = create_set_document_content_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
            requires_approval=False,
        )

        assert tool.requires_approval is False

    def test_tool_name_matches_document_type(self, mock_document, mock_task, mock_document_repo):
        """Tool name includes the document type."""
        tool = create_set_document_content_tool(
            document=mock_document,
            document_repo=mock_document_repo,
            document_parent=mock_task,
        )

        assert tool.name == "set_task_specification_content"


def _make_project_with_spec() -> Mock:
    """Build a mock Project with a project_specification document."""
    project = Mock(spec=Project)
    spec = Mock(spec=Document)
    spec.document_type = "project_specification"
    spec.content = "existing content"
    project.specification = spec
    return project


class TestBuildProjectContextDocumentTools:
    """Tests for the project context document tool builder."""

    def test_top_level_project_edit_only(self, mock_document_repo):
        project = _make_project_with_spec()

        tools = build_project_context_document_tools(project, mock_document_repo)

        assert [t.name for t in tools] == ["edit_project_specification"]

    def test_top_level_project_with_set_content(self, mock_document_repo):
        project = _make_project_with_spec()

        tools = build_project_context_document_tools(project, mock_document_repo, include_set_content=True)

        assert [t.name for t in tools] == ["set_project_specification_content", "edit_project_specification"]
