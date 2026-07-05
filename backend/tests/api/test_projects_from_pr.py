"""Tests for POST /api/projects/{project_id}/tasks/from-pr endpoint."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from devboard.db.models.codebase import Codebase
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import CodebaseRepository, DocumentRepository, ProjectRepository


@pytest.fixture
def test_project(db_session):
    """Create a test project."""
    document_repo = DocumentRepository(db_session)
    project_repo = ProjectRepository(db_session)

    spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
    project = project_repo.create(
        name="Test Project",
        description="A project for testing",
        specification=spec_doc,
    )
    db_session.commit()
    return project


@pytest.fixture
def test_codebase_with_repo(db_session, tmp_path):
    """Create a test codebase with a GitHub repository URL."""
    codebase_path = tmp_path / "from-pr-test-codebase"
    codebase_path.mkdir()

    codebase_repo = CodebaseRepository(db_session)
    codebase = codebase_repo.create(
        Codebase(
            name="From PR Test Codebase",
            description="A test codebase with a GitHub repo URL",
            local_path=str(codebase_path),
            repository_url="https://github.com/myorg/myrepo",
            default_branch="main",
        )
    )
    db_session.commit()
    return codebase


def _make_mock_pr(
    state: str = "open", title: str = "My PR Title", body: str = "PR body content", head_ref: str = "feature/my-feature"
):
    """Build a mock GitHubPR object with required attributes."""
    mock_raw_pr = MagicMock()
    mock_raw_pr.state = state
    mock_raw_pr.title = title
    mock_raw_pr.body = body
    mock_raw_pr.head.ref = head_ref

    mock_gh_pr = MagicMock()
    mock_gh_pr.pr = mock_raw_pr
    return mock_gh_pr


@pytest.fixture
def client_with_github_mock(client, db_session) -> Iterator[TestClient]:
    """Yield the test client with TaskGitService mocked out (no real git)."""
    with patch("devboard.services.task_service.TaskGitService.create_task_branch", new_callable=AsyncMock):
        yield client


class TestCreateProjectTaskFromPR:
    """Tests for POST /api/projects/{project_id}/tasks/from-pr."""

    def _mock_github(self, mock_pr):
        """Build a mock IntegrationService + GitHubIntegration that returns mock_pr."""
        mock_gh_repo = AsyncMock()
        mock_gh_repo.get_pull_request = AsyncMock(return_value=mock_pr)

        mock_github = AsyncMock()
        mock_github.get_repository = AsyncMock(return_value=mock_gh_repo)

        mock_integration_service = MagicMock()
        mock_integration_service.get_integration_instance.return_value = mock_github
        return mock_integration_service

    def test_valid_open_pr_creates_task(
        self, client_with_github_mock, db_session, test_project, test_codebase_with_repo
    ):
        """A valid open PR URL creates a task with correct fields and PR_OPEN status."""
        mock_pr = _make_mock_pr(
            state="open",
            title="Add authentication",
            body="Implements OAuth2 login",
            head_ref="feature/auth",
        )
        mock_integration_service = self._mock_github(mock_pr)

        from devboard.api.dependencies.services import get_integration_service
        from devboard.api.main import app

        app.dependency_overrides[get_integration_service] = lambda: mock_integration_service
        try:
            response = client_with_github_mock.post(
                f"/api/projects/{test_project.id}/tasks/from-pr",
                json={"pr_url": "https://github.com/myorg/myrepo/pull/42"},
            )
        finally:
            app.dependency_overrides.pop(get_integration_service, None)

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["title"] == "Add authentication"
        assert data["status"] == TaskStatus.PR_OPEN.value
        assert data["github_pr_number"] == 42
        assert data["project_id"] == test_project.id
        assert data["codebase_id"] == test_codebase_with_repo.id
        assert "id" in data
        assert "conversation_id" in data

    def test_closed_pr_returns_400(self, client_with_github_mock, db_session, test_project, test_codebase_with_repo):
        """A closed/merged PR returns a 400 error."""
        mock_pr = _make_mock_pr(state="closed")
        mock_integration_service = self._mock_github(mock_pr)

        from devboard.api.dependencies.services import get_integration_service
        from devboard.api.main import app

        app.dependency_overrides[get_integration_service] = lambda: mock_integration_service
        try:
            response = client_with_github_mock.post(
                f"/api/projects/{test_project.id}/tasks/from-pr",
                json={"pr_url": "https://github.com/myorg/myrepo/pull/10"},
            )
        finally:
            app.dependency_overrides.pop(get_integration_service, None)

        assert response.status_code == 400
        assert "not open" in response.json()["detail"].lower()

    def test_unknown_repository_returns_400(
        self, client_with_github_mock, db_session, test_project, test_codebase_with_repo
    ):
        """A PR URL for an unregistered repo returns a 400 error."""
        mock_pr = _make_mock_pr(state="open")
        mock_integration_service = self._mock_github(mock_pr)

        from devboard.api.dependencies.services import get_integration_service
        from devboard.api.main import app

        app.dependency_overrides[get_integration_service] = lambda: mock_integration_service
        try:
            response = client_with_github_mock.post(
                f"/api/projects/{test_project.id}/tasks/from-pr",
                json={"pr_url": "https://github.com/someoneelse/unknownrepo/pull/5"},
            )
        finally:
            app.dependency_overrides.pop(get_integration_service, None)

        assert response.status_code == 400
        assert "no registered codebase" in response.json()["detail"].lower()

    def test_invalid_pr_url_format_returns_422(self, client_with_github_mock, db_session, test_project):
        """An invalid PR URL (not a GitHub pull request URL) returns 422."""
        response = client_with_github_mock.post(
            f"/api/projects/{test_project.id}/tasks/from-pr",
            json={"pr_url": "https://github.com/myorg/myrepo"},
        )

        assert response.status_code == 422

    def test_nonexistent_project_returns_404(self, client_with_github_mock, db_session):
        """A non-existent project_id returns 404."""
        response = client_with_github_mock.post(
            "/api/projects/99999/tasks/from-pr",
            json={"pr_url": "https://github.com/myorg/myrepo/pull/1"},
        )

        assert response.status_code == 404

    def test_pr_body_used_as_spec_content(
        self, client_with_github_mock, db_session, test_project, test_codebase_with_repo
    ):
        """The PR body is used as the task's specification content."""
        mock_pr = _make_mock_pr(
            state="open",
            title="Feature X",
            body="## Description\n\nThis PR does X.",
            head_ref="feature/x",
        )
        mock_integration_service = self._mock_github(mock_pr)

        from devboard.api.dependencies.services import get_integration_service
        from devboard.api.main import app
        from devboard.db.repositories import DocumentRepository

        app.dependency_overrides[get_integration_service] = lambda: mock_integration_service
        try:
            response = client_with_github_mock.post(
                f"/api/projects/{test_project.id}/tasks/from-pr",
                json={"pr_url": "https://github.com/myorg/myrepo/pull/7"},
            )
        finally:
            app.dependency_overrides.pop(get_integration_service, None)

        assert response.status_code == 200, response.text
        data = response.json()

        # Verify spec document was created with the PR body
        doc_repo = DocumentRepository(db_session)
        spec_doc = doc_repo.get_by_id(data["specification_document_id"])
        assert spec_doc is not None
        assert spec_doc.content == "## Description\n\nThis PR does X."

    def test_empty_pr_body_creates_empty_spec(
        self, client_with_github_mock, db_session, test_project, test_codebase_with_repo
    ):
        """A PR with no body creates a task with empty spec content."""
        mock_pr = _make_mock_pr(state="open", body=None, title="Empty body PR", head_ref="feature/empty")
        mock_pr.pr.body = None
        mock_integration_service = self._mock_github(mock_pr)

        from devboard.api.dependencies.services import get_integration_service
        from devboard.api.main import app

        app.dependency_overrides[get_integration_service] = lambda: mock_integration_service
        try:
            response = client_with_github_mock.post(
                f"/api/projects/{test_project.id}/tasks/from-pr",
                json={"pr_url": "https://github.com/myorg/myrepo/pull/8"},
            )
        finally:
            app.dependency_overrides.pop(get_integration_service, None)

        assert response.status_code == 200, response.text
