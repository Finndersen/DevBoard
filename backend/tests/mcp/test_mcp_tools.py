"""Unit tests for MCP server tools."""

import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest import fixture

from devboard.db.models import Codebase, Project, Task
from devboard.db.models.task import TaskStatus
from devboard.mcp import server as mcp_server


@fixture
def mock_projects():
    """Mock Project instances for testing."""
    project1 = Mock(spec=Project)
    project1.id = 1
    project1.name = "Test Project 1"
    project1.description = "Description 1"
    project1.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)

    project2 = Mock(spec=Project)
    project2.id = 2
    project2.name = "Test Project 2"
    project2.description = "Description 2"
    project2.created_at = datetime.datetime(2024, 1, 2, tzinfo=datetime.UTC)

    return [project1, project2]


@fixture
def mock_tasks():
    """Mock Task instances for testing."""
    task1 = Mock(spec=Task)
    task1.id = 1
    task1.title = "Test Task 1"
    task1.status = TaskStatus.PLANNING
    task1.project_id = 1
    task1.codebase_id = None
    task1.remote_task_id = None
    task1.created_at = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)

    task2 = Mock(spec=Task)
    task2.id = 2
    task2.title = "Test Task 2"
    task2.status = TaskStatus.PLANNING
    task2.project_id = 1
    task2.codebase_id = 1
    task2.remote_task_id = "JIRA-123"
    task2.created_at = datetime.datetime(2024, 1, 2, tzinfo=datetime.UTC)

    task3 = Mock(spec=Task)
    task3.id = 3
    task3.title = "Test Task 3"
    task3.status = TaskStatus.IMPLEMENTING
    task3.project_id = 2
    task3.codebase_id = 1
    task3.remote_task_id = None
    task3.created_at = datetime.datetime(2024, 1, 3, tzinfo=datetime.UTC)

    return [task1, task2, task3]


@fixture
def mock_codebase():
    """Mock Codebase instance for testing."""
    codebase = Mock(spec=Codebase)
    codebase.id = 1
    codebase.name = "Test Codebase"
    codebase.description = "Test codebase description"
    codebase.local_path = "/tmp/test-codebase"
    return codebase


class TestGetProjects:
    """Tests for get_projects MCP tool."""

    @pytest.mark.asyncio
    async def test_get_projects_success(self, mock_projects):
        """Test successful retrieval of projects."""
        with (
            patch("devboard.mcp.server.get_mcp_db_session") as mock_session,
            patch("devboard.mcp.server.ProjectRepository") as mock_repo_class,
        ):
            # Setup mocks
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_repo = Mock()
            mock_repo.get_all.return_value = mock_projects
            mock_repo_class.return_value = mock_repo

            # Call the tool
            result = await mcp_server.get_projects.fn()

            # Verify
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["id"] == 1
            assert result[0]["name"] == "Test Project 1"
            assert result[0]["description"] == "Description 1"
            assert result[0]["created_at"] == "2024-01-01T00:00:00+00:00"
            assert result[1]["id"] == 2

            # Verify repository was called
            mock_repo.get_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_projects_empty(self):
        """Test retrieval when no projects exist."""
        with (
            patch("devboard.mcp.server.get_mcp_db_session") as mock_session,
            patch("devboard.mcp.server.ProjectRepository") as mock_repo_class,
        ):
            # Setup mocks
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_repo = Mock()
            mock_repo.get_all.return_value = []
            mock_repo_class.return_value = mock_repo

            # Call the tool
            result = await mcp_server.get_projects.fn()

            # Verify
            assert isinstance(result, list)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_projects_error(self):
        """Test error handling when database query fails."""
        with (
            patch("devboard.mcp.server.get_mcp_db_session") as mock_session,
            patch("devboard.mcp.server.ProjectRepository") as mock_repo_class,
        ):
            # Setup mocks to raise exception
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_repo = Mock()
            mock_repo.get_all.side_effect = Exception("Database error")
            mock_repo_class.return_value = mock_repo

            # Call the tool - should raise the exception
            with pytest.raises(Exception, match="Database error"):
                await mcp_server.get_projects.fn()


class TestGetTasks:
    """Tests for get_tasks MCP tool."""

    @pytest.mark.asyncio
    async def test_get_tasks_for_project(self, mock_tasks):
        """Test retrieval of tasks for a specific project."""
        project_tasks = [mock_tasks[0], mock_tasks[1]]  # Tasks for project 1

        with (
            patch("devboard.mcp.server.get_mcp_db_session") as mock_session,
            patch("devboard.mcp.server.TaskRepository") as mock_repo_class,
        ):
            # Setup mocks
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_repo = Mock()
            mock_repo.get_for_project.return_value = project_tasks
            mock_repo_class.return_value = mock_repo

            # Call the tool with project ID
            result = await mcp_server.get_tasks.fn(project_id=1)

            # Verify
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["id"] == 1
            assert result[0]["title"] == "Test Task 1"
            assert result[0]["status"] == "planning"
            assert result[0]["project_id"] == 1
            assert result[1]["project_id"] == 1

            # Verify correct repository method was called
            mock_repo.get_for_project.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_tasks_empty_project(self):
        """Test retrieval when project has no tasks."""
        with (
            patch("devboard.mcp.server.get_mcp_db_session") as mock_session,
            patch("devboard.mcp.server.TaskRepository") as mock_repo_class,
        ):
            # Setup mocks
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_repo = Mock()
            mock_repo.get_for_project.return_value = []
            mock_repo_class.return_value = mock_repo

            # Call the tool
            result = await mcp_server.get_tasks.fn(project_id=1)

            # Verify
            assert isinstance(result, list)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_tasks_error(self):
        """Test error handling when database query fails."""
        with (
            patch("devboard.mcp.server.get_mcp_db_session") as mock_session,
            patch("devboard.mcp.server.TaskRepository") as mock_repo_class,
        ):
            # Setup mocks to raise exception
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_repo = Mock()
            mock_repo.get_for_project.side_effect = Exception("Database error")
            mock_repo_class.return_value = mock_repo

            # Call the tool - should raise the exception
            with pytest.raises(Exception, match="Database error"):
                await mcp_server.get_tasks.fn(project_id=1)


class TestInvestigateCodebase:
    """Tests for investigate_codebase MCP tool."""

    @pytest.mark.asyncio
    async def test_investigate_codebase_success(self, mock_codebase):
        """Test successful codebase investigation."""
        mock_investigation_result = "Investigation results with file paths and details"

        with (
            patch("devboard.mcp.server.get_mcp_db_session") as mock_session,
            patch("devboard.mcp.server.CodebaseRepository") as mock_repo_class,
            patch("devboard.mcp.server.create_agent_config_service") as mock_agent_service,
            patch("devboard.mcp.server.create_multi_codebase_investigation_tool") as mock_create_tool,
        ):
            # Setup mocks
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_repo = Mock()
            mock_repo.get_by_name.return_value = mock_codebase
            mock_repo_class.return_value = mock_repo

            mock_agent_service.return_value = Mock()

            mock_tool = Mock()
            mock_tool.function = AsyncMock(return_value=mock_investigation_result)
            mock_create_tool.return_value = mock_tool

            # Call the tool
            result = await mcp_server.investigate_codebase.fn(
                codebase_name="Test Codebase", query="How is authentication implemented?"
            )

            # Verify
            assert result == mock_investigation_result
            assert not result.startswith("Error:")

            # Verify dependencies were called correctly
            mock_repo.get_by_name.assert_called_once_with("Test Codebase")
            mock_agent_service.assert_called_once_with(mock_db)
            mock_create_tool.assert_called_once()
            mock_tool.function.assert_called_once_with(
                codebase_name="Test Codebase", query="How is authentication implemented?"
            )

    @pytest.mark.asyncio
    async def test_investigate_codebase_not_found(self):
        """Test investigation when codebase doesn't exist."""
        with (
            patch("devboard.mcp.server.get_mcp_db_session") as mock_session,
            patch("devboard.mcp.server.CodebaseRepository") as mock_repo_class,
        ):
            # Setup mocks
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_repo = Mock()
            mock_repo.get_by_name.return_value = None
            mock_repo_class.return_value = mock_repo

            # Call the tool
            result = await mcp_server.investigate_codebase.fn(codebase_name="Nonexistent", query="Some query")

            # Verify error response
            assert result.startswith("Error:")
            assert "not found" in result
            assert "Nonexistent" in result

    @pytest.mark.asyncio
    async def test_investigate_codebase_agent_error(self, mock_codebase):
        """Test error handling when investigation agent fails."""
        with (
            patch("devboard.mcp.server.get_mcp_db_session") as mock_session,
            patch("devboard.mcp.server.CodebaseRepository") as mock_repo_class,
            patch("devboard.mcp.server.create_agent_config_service") as mock_agent_service,
            patch("devboard.mcp.server.create_multi_codebase_investigation_tool") as mock_create_tool,
        ):
            # Setup mocks
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_repo = Mock()
            mock_repo.get_by_name.return_value = mock_codebase
            mock_repo_class.return_value = mock_repo

            mock_agent_service.return_value = Mock()

            # Mock tool to raise exception
            mock_tool = Mock()
            mock_tool.function = AsyncMock(side_effect=Exception("Agent execution failed"))
            mock_create_tool.return_value = mock_tool

            # Call the tool
            result = await mcp_server.investigate_codebase.fn(codebase_name="Test Codebase", query="Some query")

            # Verify error response
            assert result.startswith("Error:")
            assert "Agent execution failed" in result
