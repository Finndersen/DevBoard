"""Tests for GitHub router endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.db.models import Codebase, Configuration
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import CodebaseRepository, ConfigurationRepository
from devboard.integrations.base import IntegrationConfigurationError, IntegrationError
from devboard.integrations.github import CICheck, GitHubPR, GitHubRepository, PullRequest


@pytest.fixture
def github_config(db_session):
    """Set up GitHub integration configuration in database."""
    config_repo = ConfigurationRepository(db_session)
    config_repo.create(
        Configuration(
            key="integration.github.main",
            value_json='{"api_token": "ghp_test_token", "base_url": "https://api.github.com"}',
        )
    )
    db_session.commit()


@pytest.fixture
def codebase_with_repo(db_session, tmp_path):
    """Create a codebase DB record with a repository URL."""
    codebase_path = tmp_path / "test-repo"
    codebase_path.mkdir()

    codebase_repo = CodebaseRepository(db_session)
    codebase = Codebase(
        name="Test Repo",
        description="Test",
        local_path=str(codebase_path),
        repository_url="https://github.com/owner/repo.git",
    )
    codebase = codebase_repo.create(codebase)
    db_session.commit()
    return codebase


def _mock_github_with_prs(prs: list[PullRequest]) -> Mock:
    """Create a mock GitHubIntegration with get_user_open_pull_requests configured."""
    mock_github = Mock()
    mock_github.get_user_open_pull_requests = AsyncMock(return_value=prs)
    return mock_github


class TestGetOpenPRs:
    def test_github_not_configured(self, client):
        """Returns error when no GitHub token is configured and gh CLI is unavailable."""
        with patch("devboard.integrations.github.subprocess.run", side_effect=FileNotFoundError):
            response = client.get("/api/github/open-prs")
        assert response.status_code == 200
        data = response.json()
        assert data["prs"] == []
        assert len(data["errors"]) == 1
        assert "github" in data["errors"][0].lower()

    def test_returns_open_prs(self, client, codebase_with_repo, github_config):
        """Returns open PRs authored by the current user."""
        mock_github = _mock_github_with_prs(
            [
                PullRequest(
                    number=1,
                    title="Fix bug",
                    html_url="https://github.com/owner/repo/pull/1",
                    mergeable_state="CLEAN",
                    repo_full_name="owner/repo",
                    updated_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
                    review_decision="APPROVED",
                    ci_status="SUCCESS",
                    comment_count=3,
                ),
                PullRequest(
                    number=2,
                    title="Add feature",
                    html_url="https://github.com/owner/repo/pull/2",
                    mergeable_state="DIRTY",
                    repo_full_name="owner/repo",
                    updated_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
                    review_decision="APPROVED",
                    ci_status="SUCCESS",
                    comment_count=3,
                ),
            ]
        )

        with patch(
            "devboard.api.routers.github.IntegrationService.get_integration_instance",
            return_value=mock_github,
        ):
            response = client.get("/api/github/open-prs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["prs"]) == 2
        assert data["errors"] == []

        pr1 = data["prs"][0]
        assert pr1["pr_status"]["pr_number"] == 1
        assert pr1["pr_status"]["title"] == "Fix bug"
        assert pr1["pr_status"]["repo_full_name"] == "owner/repo"
        assert pr1["pr_status"]["state"] == "OPEN"
        assert pr1["pr_status"]["merged"] is False
        assert pr1["associated_task"] is None

        pr2 = data["prs"][1]
        assert pr2["pr_status"]["pr_number"] == 2
        assert pr2["pr_status"]["mergeable_state"] == "DIRTY"

    def test_enriches_prs_with_codebase_info(self, client, codebase_with_repo, github_config):
        """PRs from configured codebases get codebase_id, others get null."""
        mock_github = _mock_github_with_prs(
            [
                PullRequest(
                    number=1,
                    title="Our repo PR",
                    html_url="https://github.com/owner/repo/pull/1",
                    mergeable_state="CLEAN",
                    repo_full_name="owner/repo",
                    updated_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
                    review_decision="APPROVED",
                    ci_status="SUCCESS",
                    comment_count=3,
                ),
                PullRequest(
                    number=5,
                    title="Other repo PR",
                    html_url="https://github.com/other/project/pull/5",
                    mergeable_state="CLEAN",
                    repo_full_name="other/project",
                    updated_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
                    review_decision="APPROVED",
                    ci_status="SUCCESS",
                    comment_count=3,
                ),
            ]
        )

        with patch(
            "devboard.api.routers.github.IntegrationService.get_integration_instance",
            return_value=mock_github,
        ):
            response = client.get("/api/github/open-prs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["prs"]) == 2
        assert data["prs"][0]["pr_status"]["pr_number"] == 1
        assert data["prs"][0]["associated_task"] is None
        assert data["prs"][1]["pr_status"]["pr_number"] == 5
        assert data["prs"][1]["associated_task"] is None

    def test_correlates_prs_with_tasks(self, client, db_session, codebase_with_repo, github_config):
        """PRs are correlated with DevBoard tasks by pr_number + codebase_id."""
        from devboard.db.models.document import DocumentType
        from devboard.db.repositories import DocumentRepository, ProjectRepository, TaskRepository

        # Create a task linked to PR #1
        doc_repo = DocumentRepository(db_session)
        proj_repo = ProjectRepository(db_session)
        task_repo = TaskRepository(db_session)

        spec_doc = doc_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = proj_repo.create(name="Test Project", description="test", specification=spec_doc)
        task_spec = doc_repo.create(DocumentType.TASK_SPECIFICATION, "spec")
        task = task_repo.create(
            project_id=project.id,
            title="My Task",
            specification=task_spec,
            base_branch="main",
            codebase_id=codebase_with_repo.id,
            branch_name="task-branch",
            status=TaskStatus.PR_OPEN,
        )
        task.github_pr_number = 1
        db_session.commit()

        mock_github = _mock_github_with_prs(
            [
                PullRequest(
                    number=1,
                    title="Fix bug",
                    html_url="https://github.com/owner/repo/pull/1",
                    mergeable_state="CLEAN",
                    repo_full_name="owner/repo",
                    updated_at=datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC),
                    review_decision="APPROVED",
                    ci_status="SUCCESS",
                    comment_count=3,
                ),
            ]
        )

        with patch(
            "devboard.api.routers.github.IntegrationService.get_integration_instance",
            return_value=mock_github,
        ):
            response = client.get("/api/github/open-prs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["prs"]) == 1
        assert data["prs"][0]["associated_task"]["task_id"] == task.id
        assert data["prs"][0]["associated_task"]["task_title"] == "My Task"
        assert data["prs"][0]["associated_task"]["codebase_id"] == codebase_with_repo.id

    def test_graphql_error_returns_error(self, client, codebase_with_repo, github_config):
        """GraphQL errors are returned in the errors list."""
        mock_github = Mock()
        mock_github.get_user_open_pull_requests = AsyncMock(
            side_effect=IntegrationError("GitHub GraphQL error: rate limited")
        )

        with patch(
            "devboard.api.routers.github.IntegrationService.get_integration_instance",
            return_value=mock_github,
        ):
            response = client.get("/api/github/open-prs")

        assert response.status_code == 200
        data = response.json()
        assert data["prs"] == []
        assert len(data["errors"]) == 1


class TestGetPRDetail:
    def test_codebase_not_found(self, client):
        """Returns 404 for non-existent codebase."""
        response = client.get("/api/github/prs/9999/1/detail")
        assert response.status_code == 404

    def test_codebase_no_repo_url(self, client, test_codebase):
        """Returns 400 when codebase has no repository URL."""
        response = client.get(f"/api/github/prs/{test_codebase.id}/1/detail")
        assert response.status_code == 400
        assert "repository URL" in response.json()["detail"]

    def test_returns_pr_detail(self, client, codebase_with_repo, github_config):
        """Returns detailed PR status with CI checks and reviews."""
        mock_github = Mock()
        mock_repo = Mock(spec=GitHubRepository)
        mock_pr = Mock(spec=GitHubPR)

        mock_github.get_pull_request_status = AsyncMock(
            return_value=PullRequest(
                number=1,
                title="Test PR",
                html_url="https://github.com/owner/repo/pull/1",
                mergeable_state="CLEAN",
                repo_full_name="owner/repo",
                updated_at=datetime(2026, 1, 1, tzinfo=UTC),
                review_decision=None,
                ci_status="SUCCESS",
                comment_count=0,
                ci_checks=[CICheck(context="ci/test", state="success", description="Tests passed")],
            )
        )

        mock_review = Mock()
        mock_review.user = Mock()
        mock_review.user.login = "reviewer1"
        mock_review.state = "APPROVED"
        mock_review.body = "LGTM"
        mock_pr.get_reviews = AsyncMock(return_value=[mock_review])
        mock_pr.get_comments = AsyncMock(return_value=[Mock(), Mock()])

        mock_repo.get_pull_request = AsyncMock(return_value=mock_pr)
        mock_github.get_repository_from_url = AsyncMock(return_value=mock_repo)

        with patch(
            "devboard.api.routers.github.IntegrationService.get_integration_instance",
            return_value=mock_github,
        ):
            response = client.get(f"/api/github/prs/{codebase_with_repo.id}/1/detail")

        assert response.status_code == 200
        data = response.json()
        assert data == {
            "ci_status": "SUCCESS",
            "checks": [{"name": "ci/test", "state": "success", "description": "Tests passed"}],
            "reviews": [{"author": "reviewer1", "state": "APPROVED", "body": "LGTM"}],
            "review_comment_count": 2,
        }

    def test_github_not_configured(self, client, codebase_with_repo):
        """Returns 400 when GitHub integration is not configured."""
        with patch(
            "devboard.api.routers.github.IntegrationService.get_integration_instance",
            side_effect=IntegrationConfigurationError("Not configured"),
        ):
            response = client.get(f"/api/github/prs/{codebase_with_repo.id}/1/detail")

        assert response.status_code == 400
