"""Tests for task query tools."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
import toons
from pydantic_ai import ModelRetry, Tool

from devboard.agents.tools.task_tools import (
    MAX_TASKS_LIMIT,
    _format_tasks_as_toon,
    _task_to_toon_record,
    create_create_task_tool,
    create_edit_own_task_tool,
    create_edit_task_tool,
    create_list_tasks_tool,
    create_view_task_details_tool,
)
from devboard.db.models import Codebase, CustomFieldDefinition, CustomFieldType, Document, Project, Task, TaskStatus
from devboard.db.repositories.codebase import CodebaseRepository
from devboard.db.repositories.document import DocumentRepository
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
def mock_task(mock_codebase, mock_project):
    """Create a mock Task with minimal fields."""
    task = Mock(spec=Task)
    task.id = 1
    task.project_id = 1
    task.project = mock_project
    task.initiative = None
    task.initiative_id = None
    task.title = "Implement feature X"
    task.status = TaskStatus.PLANNING
    task.created_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    task.codebase = mock_codebase
    task.branch_name = "implement-feature-x"
    task.base_branch = "main"
    task.github_pr_number = None
    task.custom_fields = {"priority": "high"}
    task.specification = Mock(spec=Document)
    task.specification.content = "Existing specification content."
    return task


@pytest.fixture
def mock_task_with_details(mock_codebase, mock_project):
    """Create a mock Task with all fields populated."""
    task = Mock(spec=Task)
    task.id = 2
    task.project_id = 1
    task.project = mock_project
    task.title = "Fix bug Y"
    task.status = TaskStatus.IMPLEMENTING
    task.created_at = datetime(2024, 1, 20, 14, 30, 0, tzinfo=UTC)
    task.codebase = mock_codebase
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
    service.get_custom_fields.return_value = []
    service.create_task = AsyncMock()
    service.is_task_agent_running.return_value = False
    service.is_agents_running_for_tasks.return_value = {}
    return service


@pytest.fixture
def mock_document_repo():
    """Create a mock DocumentRepository."""
    repo = Mock(spec=DocumentRepository)
    return repo


@pytest.fixture
def mock_codebase_repo(mock_codebase):
    """Create a mock CodebaseRepository returning a single codebase."""
    repo = Mock(spec=CodebaseRepository)
    repo.get_all.return_value = [mock_codebase]
    return repo


@pytest.fixture
def mock_agent_config_service():
    """Create a mock AgentConfigService."""
    from devboard.agents.agent_config_service import AgentConfigService
    from devboard.agents.config_types import ModelType

    service = Mock(spec=AgentConfigService)
    # Mock get_effective_config to return a config with valid model_type
    mock_config = Mock()
    mock_config.model = Mock()
    mock_config.model.model_type = ModelType.STANDARD
    service.get_effective_config.return_value = mock_config
    # Mock get_model_id_for_type to return a model ID string
    service.get_model_id_for_type.return_value = "anthropic:claude-sonnet-4"
    return service


class TestTaskToToonRecord:
    """Tests for _task_to_toon_record helper function."""

    def test_converts_task_to_dict(self, mock_task):
        """Converts task to dict with all required fields."""
        result = _task_to_toon_record(mock_task)

        assert result == {
            "id": 1,
            "title": "Implement feature X",
            "status": "planning",
            "created_at": "2024-01-15T10:00:00+00:00",
            "project_id": 1,
            "initiative_id": None,
            "codebase": "backend",
            "branch": "implement-feature-x",
            "agent_running": False,
            "custom_fields": '{"priority": "high"}',
        }

    def test_includes_branch_when_present(self, mock_task):
        """Includes branch name when present."""
        mock_task.branch_name = "feature/my-branch"

        result = _task_to_toon_record(mock_task)

        assert result["branch"] == "feature/my-branch"

    def test_empty_custom_fields_serializes_to_empty_object(self, mock_task):
        """Empty custom_fields serializes to empty JSON object."""
        mock_task.custom_fields = None

        result = _task_to_toon_record(mock_task)

        assert result["custom_fields"] == "{}"

    def test_initiative_task_includes_initiative_id(self, mock_task):
        """A task under an initiative reports its initiative_id."""
        mock_task.initiative_id = 7

        result = _task_to_toon_record(mock_task)

        assert result["project_id"] == 1
        assert result["initiative_id"] == 7


class TestFormatTasksAsToon:
    """Tests for _format_tasks_as_toon helper function."""

    def test_returns_no_tasks_message_when_empty(self):
        """Returns appropriate message when no tasks."""
        result = _format_tasks_as_toon([], 0)

        assert result == "No tasks found matching the filters."

    def test_formats_tasks_as_toon(self, mock_codebase):
        """Formats tasks as TOON-encoded string."""
        task1 = Mock(spec=Task)
        task1.id = 1
        task1.title = "Task 1"
        task1.status = TaskStatus.PLANNING
        task1.created_at = datetime(2024, 1, 10, tzinfo=UTC)
        task1.codebase = mock_codebase
        task1.branch_name = "feature/task-1"
        task1.custom_fields = {}

        task2 = Mock(spec=Task)
        task2.id = 2
        task2.title = "Task 2"
        task2.status = TaskStatus.IMPLEMENTING
        task2.created_at = datetime(2024, 1, 15, tzinfo=UTC)
        task2.codebase = mock_codebase
        task2.branch_name = "feature/task-2"
        task2.custom_fields = {"priority": "high"}

        result = _format_tasks_as_toon([task1, task2], 2)

        # Parse the TOON output and verify structure
        parsed = toons.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["id"] == 1
        assert parsed[0]["title"] == "Task 1"
        assert parsed[0]["status"] == "planning"
        assert parsed[0]["codebase"] == "backend"
        assert parsed[0]["branch"] == "feature/task-1"
        assert parsed[1]["id"] == 2
        assert parsed[1]["title"] == "Task 2"
        assert parsed[1]["status"] == "implementing"
        assert parsed[1]["branch"] == "feature/task-2"

    def test_shows_limit_warning_when_result_count_equals_limit(self, mock_codebase):
        """Shows warning when result count equals the limit (there may be more)."""
        task = Mock(spec=Task)
        task.id = 1
        task.title = "Task"
        task.status = TaskStatus.PLANNING
        task.created_at = datetime(2024, 1, 10, tzinfo=UTC)
        task.codebase = mock_codebase
        task.branch_name = "feature/task"
        task.custom_fields = {}

        result = _format_tasks_as_toon([task], limit=1)

        assert "Note: 1 results returned (the limit)" in result
        assert "increase max_results" in result
        # Verify the TOON data is still present before the note
        toon_data = result.split("\n\nNote:")[0]
        parsed = toons.loads(toon_data)
        assert len(parsed) == 1
        assert parsed[0]["id"] == 1


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
            limit=MAX_TASKS_LIMIT,
        )
        # Parse TOON output and verify task data
        parsed = toons.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["id"] == 1
        assert parsed[0]["title"] == "Implement feature X"
        assert parsed[0]["status"] == "planning"
        assert parsed[0]["codebase"] == "backend"
        assert parsed[0]["custom_fields"] == '{"priority": "high"}'

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
            limit=MAX_TASKS_LIMIT,
        )
        parsed = toons.loads(result)
        assert parsed[0]["title"] == "Implement feature X"

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
        parsed = toons.loads(result)
        assert parsed[0]["title"] == "Implement feature X"

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
            limit=MAX_TASKS_LIMIT,
        )
        parsed = toons.loads(result)
        assert parsed[0]["title"] == "Implement feature X"

    @pytest.mark.asyncio
    async def test_list_tasks_limit_reached_warning(self, mock_project, mock_task_service, mock_codebase):
        """Includes warning when result count equals the limit (may be more tasks)."""
        tasks = []
        for i in range(MAX_TASKS_LIMIT):
            task = Mock(spec=Task)
            task.id = i
            task.title = f"Task {i}"
            task.status = TaskStatus.PLANNING
            task.created_at = datetime(2024, 1, 1, tzinfo=UTC)
            task.codebase = mock_codebase
            task.branch_name = f"feature/task-{i}"
            task.custom_fields = {}
            tasks.append(task)

        mock_task_service.get_tasks_filtered.return_value = tasks

        tool = create_list_tasks_tool(mock_project, mock_task_service)
        result = await tool.function()

        assert f"Note: {MAX_TASKS_LIMIT} results returned (the limit)" in result
        assert "increase max_results" in result

    @pytest.mark.asyncio
    async def test_list_tasks_custom_max_results(self, mock_project, mock_task_service, mock_task):
        """Passes max_results to the service as limit."""
        mock_task_service.get_tasks_filtered.return_value = [mock_task]

        tool = create_list_tasks_tool(mock_project, mock_task_service)
        await tool.function(max_results=5)

        mock_task_service.get_tasks_filtered.assert_called_once_with(
            project_id=1,
            status_filter=None,
            created_after=None,
            created_before=None,
            codebase_name=None,
            limit=5,
        )

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
        assert "**Project:** Test Project (#1)" in result
        assert "**Initiative:**" not in result
        assert "**Codebase:** backend" in result
        assert "**Branch:** implement-feature-x" in result
        assert "**Base Branch:** main" in result

    @pytest.mark.asyncio
    async def test_view_task_details_initiative_shows_project_and_initiative(self, mock_task_service, mock_task):
        """For a task under an initiative, both the initiative and its parent project are shown."""
        initiative = Mock()
        initiative.id = 7
        initiative.name = "My Initiative"
        mock_task.initiative = initiative
        mock_task_service.get_task_by_id.return_value = mock_task

        # Global access (project=None) so the scoped-project security check is skipped.
        tool = create_view_task_details_tool(None, mock_task_service)
        result = await tool.function(task_id=1)

        assert "**Initiative:** My Initiative (#7)" in result
        assert "**Project:** Test Project (#1)" in result

    @pytest.mark.asyncio
    async def test_view_task_details_with_all_fields(self, mock_project, mock_task_service, mock_task_with_details):
        """Views task details including all optional fields."""
        mock_task_with_details.project_id = 1
        mock_task_service.get_task_by_id.return_value = mock_task_with_details

        tool = create_view_task_details_tool(mock_project, mock_task_service)
        result = await tool.function(task_id=2)

        assert "# Task #2: Fix bug Y" in result
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


class TestCreateListTasksToolGlobal:
    """Tests for create_list_tasks_tool with project=None (global access)."""

    def test_tool_creation_without_project(self, mock_task_service, mock_codebase_repo):
        """Tool is created with correct name when no project is given."""
        tool = create_list_tasks_tool(None, mock_task_service, codebase_repo=mock_codebase_repo)

        assert isinstance(tool, Tool)
        assert tool.name == "list_tasks"
        assert tool.function is not None

    def test_tool_uses_codebase_repo_for_names(self, mock_task_service, mock_codebase_repo):
        """Codebase names come from codebase_repo.get_all() when project is None."""
        create_list_tasks_tool(None, mock_task_service, codebase_repo=mock_codebase_repo)

        mock_codebase_repo.get_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tasks_no_project_id_filter(self, mock_task_service, mock_codebase_repo, mock_task):
        """Lists tasks across all projects when no project_id filter provided."""
        mock_task_service.get_tasks_filtered.return_value = [mock_task]

        tool = create_list_tasks_tool(None, mock_task_service, codebase_repo=mock_codebase_repo)
        result = await tool.function()

        mock_task_service.get_tasks_filtered.assert_called_once_with(
            project_id=None,
            status_filter=None,
            created_after=None,
            created_before=None,
            codebase_name=None,
            limit=MAX_TASKS_LIMIT,
        )
        parsed = toons.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_list_tasks_explicit_project_id_filter(self, mock_task_service, mock_codebase_repo, mock_task):
        """Passes explicit project_id filter through to the service."""
        mock_task_service.get_tasks_filtered.return_value = [mock_task]

        tool = create_list_tasks_tool(None, mock_task_service, codebase_repo=mock_codebase_repo)
        result = await tool.function(project_id=5)

        mock_task_service.get_tasks_filtered.assert_called_once_with(
            project_id=5,
            status_filter=None,
            created_after=None,
            created_before=None,
            codebase_name=None,
            limit=MAX_TASKS_LIMIT,
        )
        parsed = toons.loads(result)
        assert len(parsed) == 1

    @pytest.mark.asyncio
    async def test_list_tasks_no_matches_global(self, mock_task_service, mock_codebase_repo):
        """Returns no tasks message when no matches across all projects."""
        mock_task_service.get_tasks_filtered.return_value = []

        tool = create_list_tasks_tool(None, mock_task_service, codebase_repo=mock_codebase_repo)
        result = await tool.function()

        assert "No tasks found matching the filters" in result


class TestCreateViewTaskDetailsToolGlobal:
    """Tests for create_view_task_details_tool with project=None (global access)."""

    def test_tool_creation_without_project(self, mock_task_service):
        """Tool is created with correct name when no project is given."""
        tool = create_view_task_details_tool(None, mock_task_service)

        assert isinstance(tool, Tool)
        assert tool.name == "view_task_details"

    @pytest.mark.asyncio
    async def test_view_task_details_any_project(self, mock_task_service, mock_task):
        """Allows viewing tasks from any project when project is None."""
        mock_task.project_id = 999  # A different project from any context
        mock_task_service.get_task_by_id.return_value = mock_task

        tool = create_view_task_details_tool(None, mock_task_service)
        result = await tool.function(task_id=1)

        # No project ownership error raised
        assert "# Task #1: Implement feature X" in result
        assert "**Status:** planning" in result

    @pytest.mark.asyncio
    async def test_view_task_details_not_found_global(self, mock_task_service):
        """Raises ModelRetry when task not found, even in global mode."""
        mock_task_service.get_task_by_id.return_value = None

        tool = create_view_task_details_tool(None, mock_task_service)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(task_id=999)

        assert "Task with ID 999 not found" in str(exc_info.value)


class TestCreateCreateTaskTool:
    """Tests for create_create_task_tool."""

    def test_tool_creation(self, mock_project, mock_task_service, mock_agent_config_service):
        """Tool is created with correct name."""
        tool = create_create_task_tool(
            project=mock_project, task_service=mock_task_service, agent_config_service=mock_agent_config_service
        )

        assert isinstance(tool, Tool)
        assert tool.name == "create_task"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_create_task_basic(self, mock_project, mock_task_service, mock_task, mock_agent_config_service):
        """Creates a task with required fields and returns JSON."""
        mock_task_service.create_task.return_value = mock_task
        mock_task.branch_name = "feature/implement-feature-x"
        mock_task.base_branch = "main"

        tool = create_create_task_tool(
            project=mock_project, task_service=mock_task_service, agent_config_service=mock_agent_config_service
        )
        result = await tool.function(
            title="Implement feature X",
            codebase_name="backend",
        )

        mock_task_service.create_task.assert_called_once_with(
            project_id=1,
            title="Implement feature X",
            base_branch="main",
            codebase_id=10,
            specification_content="",
            branch_name=None,
            custom_fields=None,
            model_id_override="anthropic:claude-sonnet-4",
        )
        result_data = json.loads(result)
        assert result_data == {
            "task_id": 1,
            "title": "Implement feature X",
            "status": "planning",
            "branch_name": "feature/implement-feature-x",
            "base_branch": "main",
            "codebase_name": "backend",
            "agent_running": False,
        }

    @pytest.mark.asyncio
    async def test_create_task_with_all_options(
        self, mock_project, mock_task_service, mock_codebase, mock_task, mock_agent_config_service
    ):
        """Creates a task with all optional fields and returns JSON."""
        mock_codebase.default_branch = "develop"
        mock_task_service.create_task.return_value = mock_task
        mock_task.branch_name = "feature/my-branch"
        mock_task.base_branch = "develop"

        tool = create_create_task_tool(
            project=mock_project, task_service=mock_task_service, agent_config_service=mock_agent_config_service
        )
        result = await tool.function(
            title="Implement feature X",
            codebase_name="backend",
            specification_content="Task specification here",
            base_branch="develop",
            branch_name="feature/my-branch",
            custom_fields={"priority": "high"},
        )

        mock_task_service.create_task.assert_called_once_with(
            project_id=1,
            title="Implement feature X",
            base_branch="develop",
            codebase_id=10,
            specification_content="Task specification here",
            branch_name="feature/my-branch",
            custom_fields={"priority": "high"},
            model_id_override="anthropic:claude-sonnet-4",
        )
        result_data = json.loads(result)
        assert result_data["task_id"] == 1
        assert result_data["branch_name"] == "feature/my-branch"
        assert result_data["codebase_name"] == "backend"

    @pytest.mark.asyncio
    async def test_create_task_codebase_not_found(self, mock_project, mock_task_service, mock_agent_config_service):
        """Raises ModelRetry when codebase not found."""
        tool = create_create_task_tool(
            project=mock_project, task_service=mock_task_service, agent_config_service=mock_agent_config_service
        )

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(
                title="New task",
                codebase_name="nonexistent",
            )

        assert "Codebase 'nonexistent' not found" in str(exc_info.value)
        mock_task_service.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_task_uses_codebase_default_branch(
        self, mock_project, mock_task_service, mock_codebase, mock_task, mock_agent_config_service
    ):
        """Uses codebase default branch when base_branch not provided."""
        mock_codebase.default_branch = "develop"
        mock_task_service.create_task.return_value = mock_task
        mock_task.branch_name = "feature/task"
        mock_task.base_branch = "develop"

        tool = create_create_task_tool(
            project=mock_project, task_service=mock_task_service, agent_config_service=mock_agent_config_service
        )
        await tool.function(
            title="New task",
            codebase_name="backend",
        )

        call_args = mock_task_service.create_task.call_args
        assert call_args.kwargs["base_branch"] == "develop"

    @pytest.mark.asyncio
    async def test_create_task_service_exception(self, mock_project, mock_task_service, mock_agent_config_service):
        """Raises ModelRetry when task service raises exception."""
        mock_task_service.create_task.side_effect = ValueError("Invalid task data")

        tool = create_create_task_tool(
            project=mock_project, task_service=mock_task_service, agent_config_service=mock_agent_config_service
        )

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

    def test_create_task_tool_schema_no_custom_fields(self, mock_project, mock_task_service, mock_agent_config_service):
        """Verifies create_task tool schema omits custom_fields when no definitions exist."""
        tool = create_create_task_tool(mock_project, mock_task_service, mock_agent_config_service)
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

        # custom_fields should be omitted when no definitions exist
        assert "custom_fields" not in props

    def test_create_task_tool_schema_with_custom_fields(
        self, mock_project, mock_task_service, mock_agent_config_service
    ):
        """Verifies custom_fields schema exposes typed properties from definitions."""
        priority_def = Mock(spec=CustomFieldDefinition)
        priority_def.name = "priority"
        priority_def.type = CustomFieldType.ENUM
        priority_def.options = ["low", "medium", "high"]
        priority_def.description = "Task priority level"
        priority_def.mandatory = True

        notes_def = Mock(spec=CustomFieldDefinition)
        notes_def.name = "notes"
        notes_def.type = CustomFieldType.TEXT
        notes_def.options = None
        notes_def.description = "Additional notes"
        notes_def.mandatory = False

        is_urgent_def = Mock(spec=CustomFieldDefinition)
        is_urgent_def.name = "is_urgent"
        is_urgent_def.type = CustomFieldType.BOOLEAN
        is_urgent_def.options = None
        is_urgent_def.description = None
        is_urgent_def.mandatory = False

        definitions = [priority_def, notes_def, is_urgent_def]

        mock_task_service.get_custom_fields.return_value = definitions
        tool = create_create_task_tool(mock_project, mock_task_service, mock_agent_config_service)
        schema = tool.tool_def.parameters_json_schema
        props = schema["properties"]

        # custom_fields should be present with anyOf (object or null)
        assert "custom_fields" in props
        assert "anyOf" in props["custom_fields"]
        object_schemas = [s for s in props["custom_fields"]["anyOf"] if s.get("type") == "object"]
        assert len(object_schemas) == 1

        cf_schema = object_schemas[0]
        cf_props = cf_schema["properties"]

        # priority: enum field with options and description, mandatory
        assert cf_props["priority"] == {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Task priority level",
        }

        # notes: text field with description, not mandatory
        assert cf_props["notes"] == {
            "type": "string",
            "description": "Additional notes",
        }

        # is_urgent: boolean field without description, not mandatory
        assert cf_props["is_urgent"] == {"type": "boolean"}

        # Only mandatory fields in required
        assert cf_schema["required"] == ["priority"]
        assert cf_schema["additionalProperties"] is False

    def test_create_task_tool_schema_custom_fields_no_mandatory(
        self, mock_project, mock_task_service, mock_agent_config_service
    ):
        """Verifies custom_fields schema has no required array when no mandatory fields."""
        team_def = Mock(spec=CustomFieldDefinition)
        team_def.name = "team"
        team_def.type = CustomFieldType.TEXT
        team_def.options = None
        team_def.description = None
        team_def.mandatory = False

        definitions = [team_def]

        mock_task_service.get_custom_fields.return_value = definitions
        tool = create_create_task_tool(mock_project, mock_task_service, mock_agent_config_service)
        schema = tool.tool_def.parameters_json_schema
        cf_anyof = schema["properties"]["custom_fields"]["anyOf"]
        cf_schema = [s for s in cf_anyof if s.get("type") == "object"][0]

        assert "required" not in cf_schema
        assert cf_schema["properties"]["team"] == {"type": "string"}

    def test_create_task_tool_schema_multiple_codebases(self, mock_task_service, mock_agent_config_service):
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

        tool = create_create_task_tool(project, mock_task_service, mock_agent_config_service)
        schema = tool.tool_def.parameters_json_schema

        # Multiple codebases use 'enum' instead of 'const'
        assert set(schema["properties"]["codebase_name"]["enum"]) == {"backend", "frontend"}

    def test_create_task_tool_schema_no_codebases(self, mock_task_service, mock_agent_config_service):
        """Verifies codebase_name has no enum/const when project has no codebases."""
        project = Mock(spec=Project)
        project.id = 1
        project.codebases = []

        tool = create_create_task_tool(project, mock_task_service, mock_agent_config_service)
        schema = tool.tool_def.parameters_json_schema

        # Should still have codebase_name but without enum/const constraint
        assert "codebase_name" in schema["properties"]
        assert "enum" not in schema["properties"]["codebase_name"]
        assert "const" not in schema["properties"]["codebase_name"]


class TestCreateEditTaskTool:
    """Tests for create_edit_task_tool."""

    def test_edit_task_tool_creation(self, mock_project, mock_task_service, mock_document_repo):
        """Tool is created with name 'edit_task'."""
        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)

        assert isinstance(tool, Tool)
        assert tool.name == "edit_task"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_edit_task_title(self, mock_project, mock_task_service, mock_document_repo, mock_task):
        """Updates task title and returns confirmation JSON."""
        mock_task_service.get_task_by_id.return_value = mock_task
        mock_task_service.update_task.return_value = mock_task
        mock_task.title = "New Title"

        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        result = await tool.function(task_id=1, title="New Title")

        mock_task_service.update_task.assert_called_once_with(mock_task, title="New Title", custom_fields=None)
        result_data = json.loads(result)
        assert result_data == {
            "task_id": 1,
            "title": "New Title",
            "custom_fields": {"priority": "high"},
            "agent_running": False,
        }

    @pytest.mark.asyncio
    async def test_edit_task_custom_fields(self, mock_project, mock_task_service, mock_document_repo, mock_task):
        """Updates custom fields and returns confirmation JSON."""
        mock_task_service.get_task_by_id.return_value = mock_task
        mock_task_service.update_task.return_value = mock_task
        mock_task.custom_fields = {"priority": "high", "team": "backend"}

        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        result = await tool.function(task_id=1, custom_fields={"team": "backend"})

        mock_task_service.update_task.assert_called_once_with(mock_task, title=None, custom_fields={"team": "backend"})
        result_data = json.loads(result)
        assert result_data == {
            "task_id": 1,
            "title": "Implement feature X",
            "custom_fields": {"priority": "high", "team": "backend"},
            "agent_running": False,
        }

    @pytest.mark.asyncio
    async def test_edit_task_specification_content(
        self, mock_project, mock_task_service, mock_document_repo, mock_task
    ):
        """Updates specification content and returns confirmation JSON with specification_updated flag."""
        mock_task_service.get_task_by_id.return_value = mock_task
        mock_task_service.update_task.return_value = mock_task

        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        result = await tool.function(task_id=1, specification_content="New specification content")

        mock_task_service.get_task_by_id.assert_called_once_with(1, with_documents=True)
        mock_document_repo.update_content.assert_called_once_with(mock_task.specification, "New specification content")
        mock_document_repo.commit.assert_called_once()
        result_data = json.loads(result)
        assert result_data["specification_updated"] is True
        assert result_data["task_id"] == 1
        assert result_data["agent_running"] is False

    @pytest.mark.asyncio
    async def test_edit_task_specification_content_empty(
        self, mock_project, mock_task_service, mock_document_repo, mock_task
    ):
        """Raises ModelRetry when specification_content is empty/whitespace."""
        mock_task_service.get_task_by_id.return_value = mock_task

        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(task_id=1, specification_content="   ")

        assert "specification_content cannot be empty" in str(exc_info.value)
        mock_document_repo.update_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_edit_task_nothing_to_update(self, mock_project, mock_task_service, mock_document_repo):
        """Raises ModelRetry when no fields provided to update."""
        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(task_id=1)

        assert "No fields to update" in str(exc_info.value)
        mock_task_service.get_task_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_edit_task_not_found(self, mock_project, mock_task_service, mock_document_repo):
        """Raises ModelRetry when task not found."""
        mock_task_service.get_task_by_id.return_value = None

        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(task_id=999, title="New Title")

        assert "Task with ID 999 not found" in str(exc_info.value)
        mock_task_service.update_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_edit_task_wrong_project(self, mock_project, mock_task_service, mock_document_repo, mock_task):
        """Raises ModelRetry when task belongs to a different project."""
        mock_task.project_id = 999
        mock_task_service.get_task_by_id.return_value = mock_task

        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(task_id=1, title="New Title")

        assert "does not belong to this project" in str(exc_info.value)
        mock_task_service.update_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_edit_task_title_and_specification_content(
        self, mock_project, mock_task_service, mock_document_repo, mock_task
    ):
        """Updates both title and specification content in a single call."""
        mock_task_service.get_task_by_id.return_value = mock_task
        mock_task_service.update_task.return_value = mock_task
        mock_task.title = "New Title"

        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        result = await tool.function(task_id=1, title="New Title", specification_content="New spec")

        mock_task_service.update_task.assert_called_once_with(mock_task, title="New Title", custom_fields=None)
        mock_document_repo.update_content.assert_called_once_with(mock_task.specification, "New spec")
        mock_document_repo.commit.assert_called_once()
        result_data = json.loads(result)
        assert result_data == {
            "task_id": 1,
            "title": "New Title",
            "custom_fields": {"priority": "high"},
            "specification_updated": True,
            "agent_running": False,
        }

    @pytest.mark.asyncio
    async def test_edit_task_empty_specification_does_not_update_title(
        self, mock_project, mock_task_service, mock_document_repo, mock_task
    ):
        """Empty specification_content raises ModelRetry before any mutations occur."""
        mock_task_service.get_task_by_id.return_value = mock_task

        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(task_id=1, title="New Title", specification_content="   ")

        assert "specification_content cannot be empty" in str(exc_info.value)
        mock_task_service.update_task.assert_not_called()
        mock_document_repo.update_content.assert_not_called()


class TestEditTaskToolSchemas:
    """Tests for edit_task tool schema construction."""

    def test_edit_task_schema_has_task_id_required(self, mock_project, mock_task_service, mock_document_repo):
        """task_id is required; no other fields are required."""
        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        schema = tool.tool_def.parameters_json_schema

        assert "task_id" in schema["properties"]
        assert schema["required"] == ["task_id"]

    def test_edit_task_schema_has_task_id(self, mock_project, mock_task_service, mock_document_repo):
        """task_id is present in required when using create_edit_task_tool."""
        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        schema = tool.tool_def.parameters_json_schema

        assert "task_id" in schema["properties"]
        assert "task_id" in schema["required"]

    def test_edit_task_schema_has_specification_content(self, mock_project, mock_task_service, mock_document_repo):
        """specification_content is present in schema."""
        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        schema = tool.tool_def.parameters_json_schema

        assert "specification_content" in schema["properties"]
        assert "anyOf" in schema["properties"]["specification_content"]
        assert "specification" in schema["properties"]["specification_content"]["description"].lower()

    def test_edit_task_schema_no_custom_fields(self, mock_project, mock_task_service, mock_document_repo):
        """custom_fields is omitted when no field definitions provided."""
        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        schema = tool.tool_def.parameters_json_schema

        assert "custom_fields" not in schema["properties"]

    def test_edit_task_schema_with_custom_fields_nullable(self, mock_project, mock_task_service, mock_document_repo):
        """Each custom field uses anyOf with null; no required array in custom_fields object."""
        priority_def = Mock(spec=CustomFieldDefinition)
        priority_def.name = "priority"
        priority_def.type = CustomFieldType.ENUM
        priority_def.options = ["low", "high"]
        priority_def.description = "Priority level"
        priority_def.mandatory = True

        notes_def = Mock(spec=CustomFieldDefinition)
        notes_def.name = "notes"
        notes_def.type = CustomFieldType.TEXT
        notes_def.options = None
        notes_def.description = None
        notes_def.mandatory = False

        mock_task_service.get_custom_fields.return_value = [priority_def, notes_def]
        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        schema = tool.tool_def.parameters_json_schema

        assert "custom_fields" in schema["properties"]
        cf_anyof = schema["properties"]["custom_fields"]["anyOf"]
        cf_schema = [s for s in cf_anyof if s.get("type") == "object"][0]

        # No required array (all optional for editing)
        assert "required" not in cf_schema

        # Each field uses anyOf with null
        priority_prop = cf_schema["properties"]["priority"]
        assert "anyOf" in priority_prop
        null_schemas = [s for s in priority_prop["anyOf"] if s.get("type") == "null"]
        assert len(null_schemas) == 1

        notes_prop = cf_schema["properties"]["notes"]
        assert "anyOf" in notes_prop
        null_schemas = [s for s in notes_prop["anyOf"] if s.get("type") == "null"]
        assert len(null_schemas) == 1

    def test_edit_task_schema_title_optional(self, mock_project, mock_task_service, mock_document_repo):
        """title is in schema properties but not in required."""
        tool = create_edit_task_tool(mock_project, mock_task_service, mock_document_repo)
        schema = tool.tool_def.parameters_json_schema

        assert "title" in schema["properties"]
        assert "title" not in schema.get("required", [])


class TestCreateEditOwnTaskTool:
    """Tests for create_edit_own_task_tool."""

    def test_edit_own_task_tool_creation(self, mock_task, mock_task_service, mock_document_repo):
        """Tool name is 'edit_task' and is created successfully."""
        tool = create_edit_own_task_tool(mock_task, mock_task_service, mock_document_repo)

        assert isinstance(tool, Tool)
        assert tool.name == "edit_task"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_edit_own_task_title(self, mock_task, mock_task_service, mock_document_repo):
        """Updates title via pre-bound task."""
        mock_task_service.update_task.return_value = mock_task
        mock_task.title = "Updated Title"

        tool = create_edit_own_task_tool(mock_task, mock_task_service, mock_document_repo)
        result = await tool.function(title="Updated Title")

        mock_task_service.update_task.assert_called_once_with(mock_task, title="Updated Title", custom_fields=None)
        result_data = json.loads(result)
        assert result_data["task_id"] == 1
        assert result_data["title"] == "Updated Title"
        assert result_data["agent_running"] is False

    @pytest.mark.asyncio
    async def test_edit_own_task_specification_content(self, mock_task, mock_task_service, mock_document_repo):
        """Updates specification content via pre-bound task."""
        tool = create_edit_own_task_tool(mock_task, mock_task_service, mock_document_repo)
        result = await tool.function(specification_content="New spec content")

        mock_document_repo.update_content.assert_called_once_with(mock_task.specification, "New spec content")
        mock_document_repo.commit.assert_called_once()
        result_data = json.loads(result)
        assert result_data["specification_updated"] is True
        assert result_data["task_id"] == 1
        assert result_data["agent_running"] is False

    @pytest.mark.asyncio
    async def test_edit_own_task_nothing_to_update(self, mock_task, mock_task_service, mock_document_repo):
        """Raises ModelRetry when no fields provided."""
        tool = create_edit_own_task_tool(mock_task, mock_task_service, mock_document_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function()

        assert "No fields to update" in str(exc_info.value)

    def test_edit_own_task_schema_no_task_id(self, mock_task, mock_task_service, mock_document_repo):
        """task_id is NOT in schema properties."""
        tool = create_edit_own_task_tool(mock_task, mock_task_service, mock_document_repo)
        schema = tool.tool_def.parameters_json_schema

        assert "task_id" not in schema["properties"]
        assert schema.get("required", []) == []

    def test_edit_own_task_schema_has_specification_content(self, mock_task, mock_task_service, mock_document_repo):
        """specification_content is in schema properties."""
        tool = create_edit_own_task_tool(mock_task, mock_task_service, mock_document_repo)
        schema = tool.tool_def.parameters_json_schema

        assert "specification_content" in schema["properties"]
        assert "anyOf" in schema["properties"]["specification_content"]
