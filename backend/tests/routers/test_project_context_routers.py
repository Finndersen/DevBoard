"""Tests for Q&A router endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from devboard.api.dependencies.services import get_context_assembly_service
from devboard.api.main import app
from devboard.context_providers import ContextStrategy
from devboard.services.context_assembly import (
    EagerContextData,
    NoProviderFound,
    OnDemandResourceInfo,
    ProjectContextData,
    ResourceInfo,
)


@pytest.fixture
def sample_project(db_session):
    """Sample project for testing."""
    # Use repository to create project properly
    from devboard.db.repositories import ProjectRepository

    project_repo = ProjectRepository(db_session)
    return project_repo.create(
        name="Test Project",
        description="Test project description with https://github.com/owner/repo/pull/123",
    )


@pytest.fixture
def sample_context_data():
    """Sample context data for testing."""
    return ProjectContextData(
        eager_context=[
            EagerContextData(
                uri="https://github.com/owner/repo/pull/123",
                description="Important PR",
                provider_type="github",
                data={"title": "Fix bug", "body": "Bug fix details"},
            )
        ],
        on_demand_resources=[
            OnDemandResourceInfo(
                uri="https://github.com/owner/repo",
                description="Main repository",
                provider_type="github",
                has_user_description=True,
            )
        ],
        provider_errors=[],
    )


@pytest.fixture
def mock_context_assembly_service():
    """Mock context assembly service for testing."""
    return AsyncMock()


@pytest.fixture
def client_with_mock_context_service(client, mock_context_assembly_service):
    """Client with mocked context assembly service."""
    app.dependency_overrides[get_context_assembly_service] = lambda: mock_context_assembly_service
    yield client
    # Clean up after test
    if get_context_assembly_service in app.dependency_overrides:
        del app.dependency_overrides[get_context_assembly_service]


class TestContextEndpoint:
    """Test the project context endpoint."""

    def test_get_project_context_success(
        self,
        client_with_mock_context_service,
        mock_context_assembly_service,
        db_session,
        sample_project,
        sample_context_data,
    ):
        """Test successful context retrieval."""
        # Project is already created by repository and committed

        # Setup mock service
        mock_context_assembly_service.get_project_context.return_value = sample_context_data

        response = client_with_mock_context_service.get("/api/projects/1/context?query=test")

        assert response.status_code == 200
        data = response.json()

        assert data["project_id"] == 1
        assert data["project_name"] == "Test Project"
        assert data["query"] == "test"

        # Check eager context structure
        assert len(data["eager_context"]) == 1
        eager_ctx = data["eager_context"][0]
        assert eager_ctx["uri"] == "https://github.com/owner/repo/pull/123"
        assert eager_ctx["user_description"] == "Important PR"
        assert eager_ctx["provider_type"] == "github"
        assert eager_ctx["data"] == {"title": "Fix bug", "body": "Bug fix details"}

        # Check on_demand resources structure
        assert len(data["on_demand_resources"]) == 1
        on_demand = data["on_demand_resources"][0]
        assert on_demand["uri"] == "https://github.com/owner/repo"
        assert on_demand["description"] == "Main repository"
        assert on_demand["provider_type"] == "github"
        assert on_demand["has_user_description"] is True

        # Verify service was called correctly
        mock_context_assembly_service.get_project_context.assert_called_once_with(1, "test")

    def test_get_project_context_nonexistent_project(self, client):
        """Test context endpoint with non-existent project."""
        response = client.get("/api/projects/999/context")

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]


class TestValidateResourceEndpoint:
    """Test the resource validation endpoint."""

    def test_validate_resource_success(self, client_with_mock_context_service, mock_context_assembly_service):
        """Test successful resource validation."""
        uri = "https://github.com/owner/repo/pull/123"
        mock_result = ResourceInfo(
            provider=MagicMock(provider_type="github"),
            retrieval_strategy=ContextStrategy.EAGER,
            description="Test PR description",
            uri=uri,
        )
        mock_context_assembly_service.get_resource_info.return_value = mock_result

        response = client_with_mock_context_service.post(
            "/api/projects/validate-resource",
            params={"resource_uri": uri},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["resource_uri"] == uri
        assert data["valid"] is True
        assert data["provider_type"] == "github"
        assert data["strategy"] == "EAGER"
        assert data["description"] == "Test PR description"
        assert data["error"] is None

    def test_validate_resource_invalid(self, client_with_mock_context_service, mock_context_assembly_service):
        """Test validation of invalid resource."""

        mock_context_assembly_service.get_resource_info.side_effect = NoProviderFound(
            "No provider found for this URI type"
        )
        response = client_with_mock_context_service.post(
            "/api/projects/validate-resource",
            params={"resource_uri": "invalid://resource"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert data["error"] == "No provider found for this URI type"
