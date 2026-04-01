"""Tests for ProjectService — verifies system event emission on project lifecycle."""

from unittest.mock import MagicMock

import pytest

from devboard.services.project_service import ProjectService
from devboard.services.system_event_emitter import SystemEventEmitter


@pytest.fixture
def mock_conversation_service():
    service = MagicMock()
    return service


@pytest.fixture
def mock_document_repo():
    repo = MagicMock()
    doc = MagicMock()
    doc.id = 1
    repo.create.return_value = doc
    return repo


@pytest.fixture
def mock_project_repo():
    repo = MagicMock()
    project = MagicMock()
    project.id = 10
    project.name = "Test Project"
    repo.create.return_value = project
    return repo


@pytest.fixture
def mock_system_event_emitter():
    return MagicMock(spec=SystemEventEmitter)


@pytest.fixture
def project_service(mock_conversation_service, mock_document_repo, mock_project_repo, mock_system_event_emitter):
    return ProjectService(
        conversation_service=mock_conversation_service,
        document_repo=mock_document_repo,
        project_repo=mock_project_repo,
        system_event_emitter=mock_system_event_emitter,
    )


class TestProjectServiceCreateProject:
    def test_emits_project_created_event(self, project_service, mock_project_repo, mock_system_event_emitter):
        """create_project() emits a project.created system event."""
        project = project_service.create_project(name="My Project")

        mock_system_event_emitter.emit_project_created.assert_called_once_with(project)

    def test_emits_event_after_creation(self, project_service, mock_project_repo, mock_system_event_emitter):
        """project.created is emitted after the project entity is created."""
        call_order = []
        mock_project_repo.create.side_effect = lambda **kwargs: (
            call_order.append("create"),
            mock_project_repo.create.return_value,
        )[-1]
        mock_system_event_emitter.emit_project_created.side_effect = lambda p: call_order.append("emit")

        project_service.create_project(name="Ordered Project")

        assert call_order.index("create") < call_order.index("emit")
