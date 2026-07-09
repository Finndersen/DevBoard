"""Tests for project tools."""

import json
from unittest.mock import Mock

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.project_tools import (
    create_edit_project_specification_tool,
    create_list_project_initiatives_tool,
    create_list_projects_tool,
    create_set_project_specification_content_tool,
    create_view_project_details_tool,
)
from devboard.api.schemas import DocumentEdit
from devboard.db.models import Codebase, Document, Project, Task, TaskStatus
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_codebase():
    codebase = Mock(spec=Codebase)
    codebase.id = 10
    codebase.name = "backend"
    return codebase


@pytest.fixture
def mock_specification():
    spec = Mock(spec=Document)
    spec.content = "# Project Spec\n\nThis is the project specification."
    return spec


@pytest.fixture
def mock_project(mock_codebase, mock_specification):
    project = Mock(spec=Project)
    project.id = 1
    project.name = "Test Project"
    project.description = "A test project description"
    project.codebases = [mock_codebase]
    project.specification = mock_specification
    project.parent_project_id = None
    project.parent = None
    project.initiatives = []
    project.is_initiative = False
    return project


@pytest.fixture
def mock_project_repo(mock_project):
    repo = Mock(spec=ProjectRepository)
    repo.get_all.return_value = [mock_project]
    repo.get_by_id.return_value = mock_project
    return repo


@pytest.fixture
def mock_document_repo():
    repo = Mock(spec=DocumentRepository)
    return repo


@pytest.fixture
def mock_task_service():
    service = Mock(spec=TaskService)
    service.get_project_task_summaries.return_value = ([], [])
    return service


@pytest.fixture
def mock_active_task():
    task = Mock(spec=Task)
    task.id = 5
    task.title = "Active task"
    task.status = TaskStatus.IMPLEMENTING
    return task


@pytest.fixture
def mock_completed_task():
    task = Mock(spec=Task)
    task.id = 6
    task.title = "Completed task"
    task.status = TaskStatus.COMPLETE
    return task


class TestListProjectsTool:
    def test_returns_root_projects_only(self, mock_project_repo, mock_project):
        tool = create_list_projects_tool(mock_project_repo)
        result = tool.function()

        mock_project_repo.get_all.assert_called_once_with(root_only=True)
        data = json.loads(result)
        assert data == [
            {
                "id": 1,
                "name": "Test Project",
                "description": "A test project description",
                "codebases": ["backend"],
            }
        ]

    def test_returns_empty_list_when_no_projects(self, mock_project_repo):
        mock_project_repo.get_all.return_value = []
        tool = create_list_projects_tool(mock_project_repo)
        result = tool.function()

        assert json.loads(result) == []

    def test_handles_project_with_no_codebases(self, mock_project_repo, mock_project):
        mock_project.codebases = []
        tool = create_list_projects_tool(mock_project_repo)
        result = tool.function()

        data = json.loads(result)
        assert data[0]["codebases"] == []

    def test_tool_name(self, mock_project_repo):
        tool = create_list_projects_tool(mock_project_repo)
        assert tool.name == "list_projects"


class TestListProjectInitiativesTool:
    def test_returns_initiatives_for_project(self, mock_project, mock_project_repo):
        initiative = Mock(spec=Project)
        initiative.id = 2
        initiative.name = "My Initiative"
        initiative.description = "Initiative description"
        initiative.complete = False
        mock_project_repo.get_all.return_value = [initiative]

        tool = create_list_project_initiatives_tool(mock_project, mock_project_repo)
        result = tool.function()

        mock_project_repo.get_all.assert_called_once_with(parent_project_id=mock_project.id)
        data = json.loads(result)
        assert data == [
            {
                "id": 2,
                "name": "My Initiative",
                "description": "Initiative description",
                "status": "active",
            }
        ]

    def test_shows_complete_status(self, mock_project, mock_project_repo):
        initiative = Mock(spec=Project)
        initiative.id = 3
        initiative.name = "Done Initiative"
        initiative.description = None
        initiative.complete = True
        mock_project_repo.get_all.return_value = [initiative]

        tool = create_list_project_initiatives_tool(mock_project, mock_project_repo)
        result = tool.function()

        data = json.loads(result)
        assert data[0]["status"] == "complete"

    def test_returns_empty_list_when_no_initiatives(self, mock_project, mock_project_repo):
        mock_project_repo.get_all.return_value = []
        tool = create_list_project_initiatives_tool(mock_project, mock_project_repo)
        result = tool.function()

        assert json.loads(result) == []

    def test_tool_name(self, mock_project, mock_project_repo):
        tool = create_list_project_initiatives_tool(mock_project, mock_project_repo)
        assert tool.name == "list_project_initiatives"


class TestViewProjectDetailsTool:
    def test_returns_project_details(self, mock_project_repo, mock_task_service, mock_project):
        tool = create_view_project_details_tool(mock_project_repo, mock_task_service)
        result = tool.function(project_id=1)

        data = json.loads(result)
        assert data == {
            "id": 1,
            "name": "Test Project",
            "description": "A test project description",
            "type": "project",
            "parent_project": None,
            "initiatives": [],
            "codebases": ["backend"],
            "specification_content": "# Project Spec\n\nThis is the project specification.",
            "active_tasks": [],
            "recent_completed_tasks": [],
        }

    def test_raises_model_retry_when_not_found(self, mock_project_repo, mock_task_service):
        mock_project_repo.get_by_id.return_value = None
        tool = create_view_project_details_tool(mock_project_repo, mock_task_service)

        with pytest.raises(ModelRetry, match="not found"):
            tool.function(project_id=999)

    def test_includes_active_and_completed_tasks(
        self, mock_project_repo, mock_task_service, mock_active_task, mock_completed_task
    ):
        mock_task_service.get_project_task_summaries.return_value = ([mock_active_task], [mock_completed_task])
        tool = create_view_project_details_tool(mock_project_repo, mock_task_service)
        result = tool.function(project_id=1)

        data = json.loads(result)
        assert data["active_tasks"] == [{"id": 5, "title": "Active task", "status": "implementing"}]
        assert data["recent_completed_tasks"] == [{"id": 6, "title": "Completed task", "status": "complete"}]

    def test_calls_task_service_with_project_id(self, mock_project_repo, mock_task_service):
        tool = create_view_project_details_tool(mock_project_repo, mock_task_service)
        tool.function(project_id=1)

        mock_task_service.get_project_task_summaries.assert_called_once_with(1)

    def test_tool_name(self, mock_project_repo, mock_task_service):
        tool = create_view_project_details_tool(mock_project_repo, mock_task_service)
        assert tool.name == "view_project_details"


class TestEditProjectSpecificationTool:
    def test_applies_edits_successfully(self, mock_project_repo, mock_document_repo, mock_project, mock_specification):
        mock_specification.content = "Hello world"
        tool = create_edit_project_specification_tool(mock_project_repo, mock_document_repo)
        result = tool.function(
            project_id=1,
            edits=[DocumentEdit(old_string="world", new_string="there")],
        )

        assert "successfully" in result.lower()
        mock_document_repo.update_content.assert_called_once_with(mock_specification, "Hello there")
        mock_document_repo.commit.assert_called_once()

    def test_raises_model_retry_when_project_not_found(self, mock_project_repo, mock_document_repo):
        mock_project_repo.get_by_id.return_value = None
        tool = create_edit_project_specification_tool(mock_project_repo, mock_document_repo)

        with pytest.raises(ModelRetry, match="not found"):
            tool.function(project_id=999, edits=[DocumentEdit(old_string="x", new_string="y")])

    def test_raises_model_retry_when_spec_has_no_content(
        self, mock_project_repo, mock_document_repo, mock_specification
    ):
        mock_specification.content = None
        tool = create_edit_project_specification_tool(mock_project_repo, mock_document_repo)

        with pytest.raises(ModelRetry, match="no specification content"):
            tool.function(project_id=1, edits=[DocumentEdit(old_string="x", new_string="y")])

    def test_raises_model_retry_when_edit_fails(self, mock_project_repo, mock_document_repo, mock_specification):
        mock_specification.content = "Hello world"
        tool = create_edit_project_specification_tool(mock_project_repo, mock_document_repo)

        with pytest.raises(ModelRetry, match="Failed to apply edits"):
            tool.function(
                project_id=1,
                edits=[DocumentEdit(old_string="nonexistent text", new_string="replacement")],
            )

    def test_requires_approval(self, mock_project_repo, mock_document_repo):
        tool = create_edit_project_specification_tool(mock_project_repo, mock_document_repo)
        assert tool.requires_approval is True

    def test_tool_name(self, mock_project_repo, mock_document_repo):
        tool = create_edit_project_specification_tool(mock_project_repo, mock_document_repo)
        assert tool.name == "edit_project_specification"


class TestSetProjectSpecificationContentTool:
    def test_sets_content_successfully(self, mock_project_repo, mock_document_repo, mock_project, mock_specification):
        tool = create_set_project_specification_content_tool(mock_project_repo, mock_document_repo)
        result = tool.function(project_id=1, content="New specification content")

        assert "successfully" in result.lower()
        mock_document_repo.update_content.assert_called_once_with(mock_specification, "New specification content")
        mock_document_repo.commit.assert_called_once()

    def test_raises_model_retry_when_project_not_found(self, mock_project_repo, mock_document_repo):
        mock_project_repo.get_by_id.return_value = None
        tool = create_set_project_specification_content_tool(mock_project_repo, mock_document_repo)

        with pytest.raises(ModelRetry, match="not found"):
            tool.function(project_id=999, content="Some content")

    def test_raises_model_retry_when_content_is_empty(self, mock_project_repo, mock_document_repo):
        tool = create_set_project_specification_content_tool(mock_project_repo, mock_document_repo)

        with pytest.raises(ModelRetry, match="empty"):
            tool.function(project_id=1, content="   ")

    def test_requires_approval(self, mock_project_repo, mock_document_repo):
        tool = create_set_project_specification_content_tool(mock_project_repo, mock_document_repo)
        assert tool.requires_approval is True

    def test_tool_name(self, mock_project_repo, mock_document_repo):
        tool = create_set_project_specification_content_tool(mock_project_repo, mock_document_repo)
        assert tool.name == "set_project_specification_content"
