"""Tests for task query tools."""

import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from pydantic_ai import ModelRetry, Tool

from devboard.agents.tools.task_query_tools import (
    MAX_TASKS_LIMIT,
    _format_task_summary,
    _group_and_format_tasks,
    create_create_task_tool,
    create_list_tasks_tool,
    create_view_task_details_tool,
)
from devboard.db.models import Codebase, Document, Project, Task, TaskStatus
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_codebase():
    """Create a mock Codebase."""
    codebase = Mock(spec=Codebase)
    codebase.id = 10
    codebase.name = "backend"
    codebase.default_branch = "main"
    return codebase


@pytest.fixture
def mock_project(mock_codebase):
    """Create a mock Project."""
    project = Mock(spec=Project)
    project.id = 1
    project.name = "Test Project"
    project.codebases = [mock_codebase]
    return project


@pytest.fixture
def mock_task(mock_codebase):
    """Create a mock Task with minimal fields."""
    task = Mock(spec=Task)
    task.id = 1
    task.project_id = 1
    task.title = "Implement feature X"
    task.status = TaskStatus.PLANNING
    task.created_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    task.codebase = mock_codebase
    task.remote_task_id = None
    task.branch_name = None
    task.base_branch = "main"
    task.github_pr_number = None
    task.custom_fields = None
    return task


@pytest.fixture
def mock_task_with_details(mock_codebase):
    """Create a mock Task with all fields populated."""
    task = Mock(spec=Task)
    task.id = 2
    task.project_id = 1
    task.title = "Fix bug Y"
    task.status = TaskStatus.IMPLEMENTING
    task.created_at = datetime(2024, 1, 20, 14, 30, 0, tzinfo=UTC)
    task.codebase = mock_codebase
    task.remote_task_id = "PROJ-123"
    task.branch_name = "feature/fix-bug-y"
    task.base_branch = "develop"
    task.github_pr_number = 42
    task.custom_fields = {"priority": "high"}
    # Document mocks
    task.specification = Mock(spec=Document)
    task.specification.content = "This is the specification content."
    task.implementation_plan = Mock(spec=Document)
    task.implementation_plan.content = "This is the implementation plan."
    task.change_summary = Mock(spec=Document)
    task.change_summary.content = "This is the change summary."
    return task


@pytest.fixture
def mock_task_service():
    """Create a mock TaskService."""
    service = Mock(spec=TaskService)
    service.task_repo = Mock()
    service.task_repo.db = Mock()
    return service


class TestFormatTaskSummary:
    """Tests for _format_task_summary helper function."""

    def test_formats_basic_task(self, mock_task):
        """Formats task with minimal fields."""
        result = _format_task_summary(mock_task)

        assert "**Task #1**" in result
        assert "Implement feature X" in result
        assert "Status: planning" in result
        assert "Created: 2024-01-15T10:00:00+00:00" in result
        assert "Codebase: backend" in result

    def test_includes_remote_id_when_present(self, mock_task):
        """Includes remote task ID when present."""
        mock_task.remote_task_id = "JIRA-456"

        result = _format_task_summary(mock_task)

        assert "Remote ID: JIRA-456" in result

    def test_includes_branch_when_present(self, mock_task):
        """Includes branch name when present."""
        mock_task.branch_name = "feature/my-branch"

        result = _format_task_summary(mock_task)

        assert "Branch: feature/my-branch" in result


class TestGroupAndFormatTasks:
    """Tests for _group_and_format_tasks helper function."""

    def test_returns_no_tasks_message_when_empty(self):
        """Returns appropriate message when no tasks."""
        result = _group_and_format_tasks([], 0)

        assert result == "No tasks found matching the filters."

    def test_groups_tasks_by_status(self, mock_codebase):
        """Groups tasks by status with headers."""
        task1 = Mock(spec=Task)
        task1.id = 1
        task1.title = "Task 1"
        task1.status = TaskStatus.PLANNING
        task1.created_at = datetime(2024, 1, 10, tzinfo=UTC)
        task1.codebase = mock_codebase
        task1.remote_task_id = None
        task1.branch_name = None

        task2 = Mock(spec=Task)
        task2.id = 2
        task2.title = "Task 2"
        task2.status = TaskStatus.IMPLEMENTING
        task2.created_at = datetime(2024, 1, 15, tzinfo=UTC)
        task2.codebase = mock_codebase
        task2.remote_task_id = None
        task2.branch_name = None

        result = _group_and_format_tasks([task1, task2], 2)

        assert "**Found 2 tasks:**" in result
        assert "### PLANNING (1)" in result
        assert "### IMPLEMENTING (1)" in result
        assert "Task 1" in result
        assert "Task 2" in result

    def test_shows_truncation_message_when_exceeds_limit(self, mock_codebase):
        """Shows truncation message when total exceeds limit."""
        task = Mock(spec=Task)
        task.id = 1
        task.title = "Task"
        task.status = TaskStatus.PLANNING
        task.created_at = datetime(2024, 1, 10, tzinfo=UTC)
        task.codebase = mock_codebase
        task.remote_task_id = None
        task.branch_name = None

        result = _group_and_format_tasks([task], 25)

        assert "**Showing 1 of 25 tasks.**" in result
        assert "Add filter conditions" in result


class TestCreateListTasksTool:
    """Tests for create_list_tasks_tool."""

    def test_tool_creation(self, mock_project, mock_task_service):
        """Tool is created with correct name."""
        tool = create_list_tasks_tool(mock_project, mock_task_service)

        assert isinstance(tool, Tool)
        assert tool.name == "list_tasks"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_list_tasks_no_filters(self, mock_project, mock_task_service, mock_task):
        """Lists all tasks when no filters provided."""
        mock_task_service.get_tasks_filtered.return_value = [mock_task]

        tool = create_list_tasks_tool(mock_project, mock_task_service)
        result = await tool.function()

        mock_task_service.get_tasks_filtered.assert_called_once_with(
            project_id=1,
            status_filter=None,
            created_after=None,
            created_before=None,
            codebase_name=None,
        )
        assert "Found 1 tasks" in result
        assert "Implement feature X" in result

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_filter(self, mock_project, mock_task_service, mock_task):
        """Filters tasks by status."""
        mock_task_service.get_tasks_filtered.return_value = [mock_task]

        tool = create_list_tasks_tool(mock_project, mock_task_service)
        result = await tool.function(status_filter=["planning", "implementing"])

        mock_task_service.get_tasks_filtered.assert_called_once_with(
            project_id=1,
            status_filter=[TaskStatus.PLANNING, TaskStatus.IMPLEMENTING],
            created_after=None,
            created_before=None,
            codebase_name=None,
        )
        assert "Implement feature X" in result

    @pytest.mark.asyncio
    async def test_list_tasks_with_invalid_status(self, mock_project, mock_task_service):
        """Raises ModelRetry for invalid status values."""
        tool = create_list_tasks_tool(mock_project, mock_task_service)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(status_filter=["invalid_status"])

        assert "Invalid status value" in str(exc_info.value)
        assert "Valid values:" in str(exc_info.value)
        mock_task_service.get_tasks_filtered.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_tasks_with_date_filters(self, mock_project, mock_task_service, mock_task):
        """Filters tasks by date range."""
        mock_task_service.get_tasks_filtered.return_value = [mock_task]

        tool = create_list_tasks_tool(mock_project, mock_task_service)
        result = await tool.function(
            created_after_date="2024-01-01",
            created_before_date="2024-02-01",
        )

        call_args = mock_task_service.get_tasks_filtered.call_args
        assert call_args.kwargs["created_after"] == datetime(2024, 1, 1)
        assert call_args.kwargs["created_before"] == datetime(2024, 2, 1)
        assert "Implement feature X" in result

    @pytest.mark.asyncio
    async def test_list_tasks_with_invalid_date(self, mock_project, mock_task_service):
        """Raises ModelRetry for invalid date format."""
        tool = create_list_tasks_tool(mock_project, mock_task_service)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(created_after_date="not-a-date")

        assert "Invalid date format" in str(exc_info.value)
        assert "YYYY-MM-DD" in str(exc_info.value)
        mock_task_service.get_tasks_filtered.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_tasks_with_codebase_filter(self, mock_project, mock_task_service, mock_task):
        """Filters tasks by codebase name."""
        mock_task_service.get_tasks_filtered.return_value = [mock_task]

        tool = create_list_tasks_tool(mock_project, mock_task_service)
        result = await tool.function(codebase_name="backend")

        mock_task_service.get_tasks_filtered.assert_called_once_with(
            project_id=1,
            status_filter=None,
            created_after=None,
            created_before=None,
            codebase_name="backend",
        )
        assert "Implement feature X" in result

    @pytest.mark.asyncio
    async def test_list_tasks_limits_results(self, mock_project, mock_task_service, mock_codebase):
        """Limits results to MAX_TASKS_LIMIT."""
        tasks = []
        for i in range(25):
            task = Mock(spec=Task)
            task.id = i
            task.title = f"Task {i}"
            task.status = TaskStatus.PLANNING
            task.created_at = datetime(2024, 1, i + 1, tzinfo=UTC)
            task.codebase = mock_codebase
            task.remote_task_id = None
            task.branch_name = None
            tasks.append(task)

        mock_task_service.get_tasks_filtered.return_value = tasks

        tool = create_list_tasks_tool(mock_project, mock_task_service)
        result = await tool.function()

        assert f"**Showing {MAX_TASKS_LIMIT} of 25 tasks.**" in result

    @pytest.mark.asyncio
    async def test_list_tasks_no_matches(self, mock_project, mock_task_service):
        """Returns no tasks message when no matches."""
        mock_task_service.get_tasks_filtered.return_value = []

        tool = create_list_tasks_tool(mock_project, mock_task_service)
        result = await tool.function()

        assert "No tasks found matching the filters" in result


class TestCreateViewTaskDetailsTool:
    """Tests for create_view_task_details_tool."""

    def test_tool_creation(self, mock_project, mock_task_service):
        """Tool is created with correct name."""
        tool = create_view_task_details_tool(mock_project, mock_task_service)

        assert isinstance(tool, Tool)
        assert tool.name == "view_task_details"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_view_task_details_basic(self, mock_project, mock_task_service, mock_task):
        """Views basic task details without documents."""
        mock_task_service.get_task_by_id.return_value = mock_task

        tool = create_view_task_details_tool(mock_project, mock_task_service)
        result = await tool.function(task_id=1)

        mock_task_service.get_task_by_id.assert_called_once_with(1, with_documents=False)
        assert "# Task #1: Implement feature X" in result
        assert "**Status:** planning" in result
        assert "**Codebase:** backend" in result

    @pytest.mark.asyncio
    async def test_view_task_details_with_all_fields(self, mock_project, mock_task_service, mock_task_with_details):
        """Views task details including all optional fields."""
        mock_task_with_details.project_id = 1
        mock_task_service.get_task_by_id.return_value = mock_task_with_details

        tool = create_view_task_details_tool(mock_project, mock_task_service)
        result = await tool.function(task_id=2)

        assert "# Task #2: Fix bug Y" in result
        assert "**Remote Task ID:** PROJ-123" in result
        assert "**Branch:** feature/fix-bug-y" in result
        assert "**Base Branch:** develop" in result
        assert "**GitHub PR:** #42" in result
        assert "**Custom Fields:**" in result

    @pytest.mark.asyncio
    async def test_view_task_details_task_not_found(self, mock_project, mock_task_service):
        """Raises ModelRetry when task not found."""
        mock_task_service.get_task_by_id.return_value = None

        tool = create_view_task_details_tool(mock_project, mock_task_service)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(task_id=999)

        assert "Task with ID 999 not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_view_task_details_wrong_project(self, mock_project, mock_task_service, mock_task):
        """Raises ModelRetry when task belongs to different project."""
        mock_task.project_id = 999  # Different project
        mock_task_service.get_task_by_id.return_value = mock_task

        tool = create_view_task_details_tool(mock_project, mock_task_service)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(task_id=1)

        assert "Task with ID 1 does not belong to this project" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_view_task_details_with_documents(self, mock_project, mock_task_service, mock_task_with_details):
        """Includes document contents when requested."""
        mock_task_with_details.project_id = 1
        mock_task_service.get_task_by_id.return_value = mock_task_with_details

        tool = create_view_task_details_tool(mock_project, mock_task_service)
        result = await tool.function(
            task_id=2,
            include_documents=["specification", "implementation_plan", "change_summary"],
        )

        mock_task_service.get_task_by_id.assert_called_once_with(2, with_documents=True)
        assert "## Specification" in result
        assert "This is the specification content." in result
        assert "## Implementation Plan" in result
        assert "This is the implementation plan." in result
        assert "## Change Summary" in result
        assert "This is the change summary." in result

    @pytest.mark.asyncio
    async def test_view_task_details_with_empty_documents(self, mock_project, mock_task_service, mock_task):
        """Shows placeholder for empty/missing documents."""
        mock_task.specification = None
        mock_task.implementation_plan = None
        mock_task.change_summary = None
        mock_task_service.get_task_by_id.return_value = mock_task

        tool = create_view_task_details_tool(mock_project, mock_task_service)
        result = await tool.function(
            task_id=1,
            include_documents=["specification", "implementation_plan", "change_summary"],
        )

        assert "<empty>" in result
        assert "*No implementation plan created yet.*" in result
        assert "*No change summary created yet.*" in result

    @pytest.mark.asyncio
    async def test_view_task_details_invalid_document_type(self, mock_project, mock_task_service):
        """Raises ModelRetry for invalid document types."""
        tool = create_view_task_details_tool(mock_project, mock_task_service)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(task_id=1, include_documents=["invalid_doc"])

        assert "Invalid document types:" in str(exc_info.value)
        assert "invalid_doc" in str(exc_info.value)
        assert "Valid types:" in str(exc_info.value)
        mock_task_service.get_task_by_id.assert_not_called()


class TestCreateCreateTaskTool:
    """Tests for create_create_task_tool."""

    def test_tool_creation(self, mock_project, mock_task_service):
        """Tool is created with correct name."""
        tool = create_create_task_tool(project=mock_project, task_service=mock_task_service)

        assert isinstance(tool, Tool)
        assert tool.name == "create_task"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_create_task_basic(self, mock_project, mock_task_service, mock_task):
        """Creates a task with required fields and returns JSON."""
        mock_task_service.create_task.return_value = mock_task
        mock_task.branch_name = "feature/implement-feature-x"
        mock_task.base_branch = "main"

        tool = create_create_task_tool(project=mock_project, task_service=mock_task_service)
        result = await tool.function(
            title="Implement feature X",
            codebase_name="backend",
        )

        mock_task_service.create_task.assert_called_once_with(
            project_id=1,
            title="Implement feature X",
            base_branch="main",
            codebase_id=10,
            remote_task_id=None,
            specification_content="",
            branch_name=None,
            custom_fields=None,
        )
        result_data = json.loads(result)
        assert result_data == {
            "task_id": 1,
            "title": "Implement feature X",
            "status": "planning",
            "branch_name": "feature/implement-feature-x",
            "base_branch": "main",
            "codebase_name": "backend",
        }

    @pytest.mark.asyncio
    async def test_create_task_with_all_options(self, mock_project, mock_task_service, mock_codebase, mock_task):
        """Creates a task with all optional fields and returns JSON."""
        mock_codebase.default_branch = "develop"
        mock_task_service.create_task.return_value = mock_task
        mock_task.branch_name = "feature/my-branch"
        mock_task.base_branch = "develop"

        tool = create_create_task_tool(project=mock_project, task_service=mock_task_service)
        result = await tool.function(
            title="Implement feature X",
            codebase_name="backend",
            specification_content="Task specification here",
            base_branch="develop",
            branch_name="feature/my-branch",
            remote_task_id="PROJ-456",
            custom_fields={"priority": "high"},
        )

        mock_task_service.create_task.assert_called_once_with(
            project_id=1,
            title="Implement feature X",
            base_branch="develop",
            codebase_id=10,
            remote_task_id="PROJ-456",
            specification_content="Task specification here",
            branch_name="feature/my-branch",
            custom_fields={"priority": "high"},
        )
        result_data = json.loads(result)
        assert result_data["task_id"] == 1
        assert result_data["branch_name"] == "feature/my-branch"
        assert result_data["codebase_name"] == "backend"

    @pytest.mark.asyncio
    async def test_create_task_codebase_not_found(self, mock_project, mock_task_service):
        """Raises ModelRetry when codebase not found."""
        tool = create_create_task_tool(project=mock_project, task_service=mock_task_service)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(
                title="New task",
                codebase_name="nonexistent",
            )

        assert "Codebase 'nonexistent' not found" in str(exc_info.value)
        mock_task_service.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_task_uses_codebase_default_branch(
        self, mock_project, mock_task_service, mock_codebase, mock_task
    ):
        """Uses codebase default branch when base_branch not provided."""
        mock_codebase.default_branch = "develop"
        mock_task_service.create_task.return_value = mock_task
        mock_task.branch_name = "feature/task"
        mock_task.base_branch = "develop"

        tool = create_create_task_tool(project=mock_project, task_service=mock_task_service)
        await tool.function(
            title="New task",
            codebase_name="backend",
        )

        call_args = mock_task_service.create_task.call_args
        assert call_args.kwargs["base_branch"] == "develop"

    @pytest.mark.asyncio
    async def test_create_task_service_exception(self, mock_project, mock_task_service):
        """Raises ModelRetry when task service raises exception."""
        mock_task_service.create_task.side_effect = ValueError("Invalid task data")

        tool = create_create_task_tool(project=mock_project, task_service=mock_task_service)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(
                title="New task",
                codebase_name="backend",
            )

        assert "Failed to create task:" in str(exc_info.value)
        assert "Invalid task data" in str(exc_info.value)


class TestToolSchemas:
    """Tests for tool input schema definitions."""

    def test_list_tasks_tool_schema(self, mock_project, mock_task_service):
        """Verifies list_tasks tool schema has correct parameters and descriptions."""
        tool = create_list_tasks_tool(mock_project, mock_task_service)
        schema = tool.tool_def.parameters_json_schema

        assert schema["type"] == "object"
        props = schema["properties"]

        # status_filter parameter (optional, uses anyOf for nullable array)
        assert "status_filter" in props
        status_filter = props["status_filter"]
        assert "anyOf" in status_filter
        # Should have array type in anyOf
        array_types = [t for t in status_filter["anyOf"] if t.get("type") == "array"]
        assert len(array_types) == 1
        assert "status" in status_filter["description"].lower()

        # created_after_date parameter (optional string)
        assert "created_after_date" in props
        assert "anyOf" in props["created_after_date"]
        assert "date" in props["created_after_date"]["description"].lower()

        # created_before_date parameter (optional string)
        assert "created_before_date" in props
        assert "anyOf" in props["created_before_date"]
        assert "date" in props["created_before_date"]["description"].lower()

        # codebase_name parameter - single codebase uses 'const'
        assert "codebase_name" in props
        assert props["codebase_name"]["type"] == "string"
        assert props["codebase_name"]["const"] == "backend"
        assert "codebase" in props["codebase_name"]["description"].lower()

        # No required parameters (all have defaults)
        assert schema.get("required", []) == []

    def test_list_tasks_tool_schema_multiple_codebases(self, mock_task_service):
        """Verifies codebase_name enum includes all project codebases."""
        codebase1 = Mock(spec=Codebase)
        codebase1.id = 1
        codebase1.name = "backend"
        codebase2 = Mock(spec=Codebase)
        codebase2.id = 2
        codebase2.name = "frontend"

        project = Mock(spec=Project)
        project.id = 1
        project.codebases = [codebase1, codebase2]

        tool = create_list_tasks_tool(project, mock_task_service)
        schema = tool.tool_def.parameters_json_schema

        # Multiple codebases use 'enum' instead of 'const'
        assert set(schema["properties"]["codebase_name"]["enum"]) == {"backend", "frontend"}

    def test_list_tasks_tool_schema_no_codebases(self, mock_task_service):
        """Verifies codebase_name has no enum/const when project has no codebases."""
        project = Mock(spec=Project)
        project.id = 1
        project.codebases = []

        tool = create_list_tasks_tool(project, mock_task_service)
        schema = tool.tool_def.parameters_json_schema

        # Should still have codebase_name but without enum/const constraint
        assert "codebase_name" in schema["properties"]
        assert "enum" not in schema["properties"]["codebase_name"]
        assert "const" not in schema["properties"]["codebase_name"]

    def test_view_task_details_tool_schema(self, mock_project, mock_task_service):
        """Verifies view_task_details tool schema has correct parameters and descriptions."""
        tool = create_view_task_details_tool(mock_project, mock_task_service)
        schema = tool.tool_def.parameters_json_schema

        assert schema["type"] == "object"
        props = schema["properties"]

        # task_id parameter (required)
        assert "task_id" in props
        assert props["task_id"]["type"] == "integer"
        assert "id" in props["task_id"]["description"].lower()
        assert "task_id" in schema["required"]

        # include_documents parameter (optional, uses anyOf for nullable array)
        assert "include_documents" in props
        include_docs = props["include_documents"]
        assert "anyOf" in include_docs
        # Should have array type in anyOf
        array_types = [t for t in include_docs["anyOf"] if t.get("type") == "array"]
        assert len(array_types) == 1
        assert "document" in include_docs["description"].lower()
        # Should mention valid document types
        description = include_docs["description"]
        assert "specification" in description
        assert "implementation_plan" in description
        assert "change_summary" in description

    def test_create_task_tool_schema(self, mock_project, mock_task_service):
        """Verifies create_task tool schema has correct parameters and descriptions."""
        tool = create_create_task_tool(mock_project, mock_task_service)
        schema = tool.tool_def.parameters_json_schema

        assert schema["type"] == "object"
        props = schema["properties"]

        # title parameter (required)
        assert "title" in props
        assert props["title"]["type"] == "string"
        assert "title" in props["title"]["description"].lower()
        assert "title" in schema["required"]

        # codebase_name parameter (required) - single codebase uses 'const'
        assert "codebase_name" in props
        assert props["codebase_name"]["type"] == "string"
        assert props["codebase_name"]["const"] == "backend"
        assert "codebase" in props["codebase_name"]["description"].lower()
        assert "codebase_name" in schema["required"]

        # specification_content parameter (optional, uses anyOf)
        assert "specification_content" in props
        assert "anyOf" in props["specification_content"]
        assert "specification" in props["specification_content"]["description"].lower()

        # base_branch parameter (optional, uses anyOf)
        assert "base_branch" in props
        assert "anyOf" in props["base_branch"]
        assert "branch" in props["base_branch"]["description"].lower()

        # branch_name parameter (optional, uses anyOf)
        assert "branch_name" in props
        assert "anyOf" in props["branch_name"]

        # remote_task_id parameter (optional, uses anyOf)
        assert "remote_task_id" in props
        assert "anyOf" in props["remote_task_id"]
        assert "jira" in props["remote_task_id"]["description"].lower()

        # custom_fields parameter (optional, uses anyOf)
        assert "custom_fields" in props
        assert "anyOf" in props["custom_fields"]
        # Should have object type in anyOf
        object_types = [t for t in props["custom_fields"]["anyOf"] if t.get("type") == "object"]
        assert len(object_types) == 1

    def test_create_task_tool_schema_multiple_codebases(self, mock_task_service):
        """Verifies codebase_name enum includes all project codebases."""
        codebase1 = Mock(spec=Codebase)
        codebase1.id = 1
        codebase1.name = "backend"
        codebase2 = Mock(spec=Codebase)
        codebase2.id = 2
        codebase2.name = "frontend"

        project = Mock(spec=Project)
        project.id = 1
        project.codebases = [codebase1, codebase2]

        tool = create_create_task_tool(project, mock_task_service)
        schema = tool.tool_def.parameters_json_schema

        # Multiple codebases use 'enum' instead of 'const'
        assert set(schema["properties"]["codebase_name"]["enum"]) == {"backend", "frontend"}

    def test_create_task_tool_schema_no_codebases(self, mock_task_service):
        """Verifies codebase_name has no enum/const when project has no codebases."""
        project = Mock(spec=Project)
        project.id = 1
        project.codebases = []

        tool = create_create_task_tool(project, mock_task_service)
        schema = tool.tool_def.parameters_json_schema

        # Should still have codebase_name but without enum/const constraint
        assert "codebase_name" in schema["properties"]
        assert "enum" not in schema["properties"]["codebase_name"]
        assert "const" not in schema["properties"]["codebase_name"]
