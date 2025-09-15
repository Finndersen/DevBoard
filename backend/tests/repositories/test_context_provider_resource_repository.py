import pytest
from sqlalchemy.orm import Session

from devboard.db.models import ContextProviderResource
from devboard.db.repositories import ContextProviderResourceRepository


class TestContextProviderResourceRepository:
    """Tests for ContextProviderResourceRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ContextProviderResourceRepository:
        return ContextProviderResourceRepository(db_session)

    @pytest.fixture
    def sample_resource(self) -> ContextProviderResource:
        return ContextProviderResource(
            provider_name="github",
            resource_uri="https://github.com/test/repo",
            description="Test repository",
        )

    def test_create_resource(
        self,
        repo: ContextProviderResourceRepository,
        sample_resource: ContextProviderResource,
    ):
        """Test creating a new context provider resource."""
        created = repo.create_resource(
            resource_uri=sample_resource.resource_uri,
            provider_name=sample_resource.provider_name,
            description=sample_resource.description,
        )
        assert created.id is not None
        assert created.description == "Test repository"
        assert created.provider_name == "github"

    def test_get_by_id(
        self,
        repo: ContextProviderResourceRepository,
        sample_resource: ContextProviderResource,
    ):
        """Test getting a resource by ID."""
        created = repo.create_resource(
            resource_uri=sample_resource.resource_uri,
            provider_name=sample_resource.provider_name,
            description=sample_resource.description,
        )
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.resource_uri == created.resource_uri

    def test_get_by_id_not_found(self, repo: ContextProviderResourceRepository):
        """Test getting a resource by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_resources_for_project(self, repo: ContextProviderResourceRepository):
        """Test getting resources linked to a project."""
        # Create resources using the correct API
        resource1 = repo.create_resource(
            resource_uri="https://github.com/test/repo1",
            provider_name="github",
            description="Test repo 1",
        )
        resource2 = repo.create_resource(
            resource_uri="https://jira.example.com/issue/123",
            provider_name="jira",
            description="Test issue",
        )
        resource3 = repo.create_resource(
            resource_uri="https://github.com/test/repo2",
            provider_name="github",
            description="Test repo 2",
        )

        # Link resources to projects
        repo.link_resource_to_project(resource1.id, 1)
        repo.link_resource_to_project(resource2.id, 1)
        repo.link_resource_to_project(resource3.id, 2)

        # Test getting resources for project 1
        results = repo.get_resources_for_project(1)
        assert len(results) == 2
        resource_uris = {r.resource_uri for r in results}
        assert "https://github.com/test/repo1" in resource_uris
        assert "https://jira.example.com/issue/123" in resource_uris

        # Test getting resources for project 2
        results2 = repo.get_resources_for_project(2)
        assert len(results2) == 1
        assert results2[0].resource_uri == "https://github.com/test/repo2"

    def test_update_resource(
        self,
        repo: ContextProviderResourceRepository,
        sample_resource: ContextProviderResource,
    ):
        """Test updating a context provider resource."""
        created = repo.create_resource(
            resource_uri=sample_resource.resource_uri,
            provider_name=sample_resource.provider_name,
            description=sample_resource.description,
        )
        created.provider_name = "updated_provider"
        created.resource_uri = "https://example.com/updated"

        updated = repo.update(created)
        assert updated.provider_name == "updated_provider"
        assert updated.resource_uri == "https://example.com/updated"

    def test_delete_by_id(
        self,
        repo: ContextProviderResourceRepository,
        sample_resource: ContextProviderResource,
    ):
        """Test deleting a resource by ID."""
        created = repo.create_resource(
            resource_uri=sample_resource.resource_uri,
            provider_name=sample_resource.provider_name,
            description=sample_resource.description,
        )
        result = repo.delete_resource(created.id)

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: ContextProviderResourceRepository):
        """Test deleting a resource by ID when it doesn't exist."""
        result = repo.delete_resource(999)
        assert result is False

    def test_delete_project_resource_with_cascade(self, repo: ContextProviderResourceRepository):
        """Test deleting project resource with cascade deletion when orphaned."""
        # Create resources
        resource1 = repo.create_resource(
            resource_uri="https://github.com/test/repo1",
            provider_name="github",
            description="Test repo 1",
        )
        resource2 = repo.create_resource(
            resource_uri="https://jira.example.com/issue/123",
            provider_name="jira",
            description="Test issue",
        )

        # Link both resources to project 1
        repo.link_resource_to_project(resource1.id, 1)
        repo.link_resource_to_project(resource2.id, 1)

        # Also link resource1 to project 2 (so it won't be cascade deleted)
        repo.link_resource_to_project(resource1.id, 2)

        # Delete resource1 from project 1 - should not cascade delete (still linked to project 2)
        result1 = repo.delete_project_resource(1, resource1.id)
        assert result1 is True
        assert repo.get_by_id(resource1.id) is not None  # Still exists

        # Delete resource2 from project 1 - should cascade delete (becomes orphaned)
        result2 = repo.delete_project_resource(1, resource2.id)
        assert result2 is True
        assert repo.get_by_id(resource2.id) is None  # Cascade deleted

        # Verify project 1 has no more resources
        remaining_resources = repo.get_resources_for_project(1)
        assert len(remaining_resources) == 0

        # Verify project 2 still has resource1
        project2_resources = repo.get_resources_for_project(2)
        assert len(project2_resources) == 1
        assert project2_resources[0].id == resource1.id
