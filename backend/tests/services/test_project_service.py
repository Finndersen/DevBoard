"""Tests for ProjectService — verifies system event emission on project lifecycle."""

from unittest.mock import MagicMock, patch

import pytest

from devboard.db.models.document import DocumentType
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
    @pytest.fixture(autouse=True)
    def mock_project_directory(self):
        with patch("devboard.services.project_service.ensure_project_directory"):
            yield

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

    def test_top_level_project_gets_project_specification_document(self, project_service, mock_document_repo):
        """A top-level project's document is created with type PROJECT_SPECIFICATION."""
        project_service.create_project(name="Top Level")

        mock_document_repo.create.assert_called_once_with(DocumentType.PROJECT_SPECIFICATION, "")

    def test_initiative_gets_initiative_context_document(self, project_service, mock_document_repo, mock_project_repo):
        """An initiative's document is created with type INITIATIVE_CONTEXT."""
        parent = MagicMock()
        parent.parent_project_id = None
        mock_project_repo.get_by_id.return_value = parent

        project_service.create_project(name="Initiative", parent_project_id=5)

        mock_document_repo.create.assert_called_once_with(DocumentType.INITIATIVE_CONTEXT, "")
