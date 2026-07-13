"""Tests for project lifecycle tools (complete_project, create_initiative)."""

from unittest.mock import Mock

import pytest

from devboard.agents.tools.project_tools import (
    create_complete_project_tool,
    create_create_initiative_tool,
)
from devboard.db.models import Project
from devboard.db.models.initiative import Initiative
from devboard.services.project_service import ProjectService


@pytest.fixture
def mock_project():
    project = Mock(spec=Project)
    project.id = 1
    project.name = "Test Project"
    return project


@pytest.fixture
def mock_project_service():
    return Mock(spec=ProjectService)


class TestCompleteProjectTool:
    def test_calls_service_with_project_and_summary(self, mock_project, mock_project_service):
        tool = create_complete_project_tool(mock_project, mock_project_service)
        tool.function(summary="Finished all tasks")

        mock_project_service.complete_project.assert_called_once_with(mock_project, "Finished all tasks")

    def test_returns_project_complete_message(self, mock_project, mock_project_service):
        tool = create_complete_project_tool(mock_project, mock_project_service)
        result = tool.function(summary="Done")

        assert result == "Project 'Test Project' has been marked as complete."

    def test_requires_approval(self, mock_project, mock_project_service):
        tool = create_complete_project_tool(mock_project, mock_project_service)
        assert tool.requires_approval is True

    def test_tool_name(self, mock_project, mock_project_service):
        tool = create_complete_project_tool(mock_project, mock_project_service)
        assert tool.name == "complete_project"


class TestCreateInitiativeTool:
    def test_calls_service_with_correct_args(self, mock_project, mock_project_service):
        new_initiative = Mock(spec=Initiative)
        new_initiative.id = 5
        new_initiative.name = "New Initiative"
        mock_project_service.create_initiative.return_value = new_initiative

        tool = create_create_initiative_tool(mock_project, mock_project_service)
        tool.function(name="New Initiative", description="A scoped sub-goal")

        mock_project_service.create_initiative.assert_called_once_with(
            project_id=mock_project.id,
            name="New Initiative",
            description="A scoped sub-goal",
        )

    def test_returns_initiative_created_message(self, mock_project, mock_project_service):
        new_initiative = Mock(spec=Initiative)
        new_initiative.id = 5
        new_initiative.name = "New Initiative"
        mock_project_service.create_initiative.return_value = new_initiative

        tool = create_create_initiative_tool(mock_project, mock_project_service)
        result = tool.function(name="New Initiative", description="A scoped sub-goal")

        assert result == "Initiative 'New Initiative' (ID: 5) created under project 'Test Project'."

    def test_requires_approval(self, mock_project, mock_project_service):
        tool = create_create_initiative_tool(mock_project, mock_project_service)
        assert tool.requires_approval is True

    def test_tool_name(self, mock_project, mock_project_service):
        tool = create_create_initiative_tool(mock_project, mock_project_service)
        assert tool.name == "create_initiative"
