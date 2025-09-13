"""Tests for Q&A router endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.context_providers import ContextStrategy
from devboard.db.models import Project
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


class TestContextEndpoint:
    """Test the project context endpoint."""

    @patch("devboard.api.routers.projects.context_assembly_service")
    def test_get_project_context_success(
        self, mock_context_service, client, db_session, sample_project, sample_context_data
    ):
        """Test successful context retrieval."""
        # Project is already created by repository and committed

        # Setup mock service
        mock_context_service.get_project_context = AsyncMock(
            return_value=sample_context_data
        )

        response = client.get("/api/projects/1/context?query=test")

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
        mock_context_service.get_project_context.assert_called_once_with(
            1, "test"
        )

    def test_get_project_context_nonexistent_project(self, client):
        """Test context endpoint with non-existent project."""
        response = client.get("/api/projects/999/context")

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]


class TestValidateResourceEndpoint:
    """Test the resource validation endpoint."""

    @patch("devboard.api.routers.projects.context_assembly_service")
    def test_validate_resource_success(self, mock_context_service, client):
        """Test successful resource validation."""
        uri = "https://github.com/owner/repo/pull/123"
        mock_result = ResourceInfo(
            provider=MagicMock(provider_type="github"),
            retrieval_strategy=ContextStrategy.EAGER,
            description="Test PR description",
            uri=uri,
        )
        mock_context_service.get_resource_info = AsyncMock(
            return_value=mock_result
        )

        response = client.post(
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

    @patch("devboard.api.routers.projects.context_assembly_service")
    def test_validate_resource_invalid(self, mock_context_service, client):
        """Test validation of invalid resource."""

        mock_context_service.get_resource_info = AsyncMock(
            side_effect=NoProviderFound("No provider found for this URI type")
        )
        response = client.post(
            "/api/projects/validate-resource",
            params={"resource_uri": "invalid://resource"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert data["error"] == "No provider found for this URI type"
