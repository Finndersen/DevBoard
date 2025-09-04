"""Tests for M2M resource sharing functionality."""

import pytest

from devboard.db.models import Project, Task
from devboard.db.repositories import (
    ContextProviderResourceRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.services.resource_service import ResourceService


@pytest.fixture
def test_projects_data():
    """Sample projects data for testing."""
    return [
        {
            "name": "Auth Service",
            "details": "Authentication microservice",
            "current_status": "active",
        },
        {
            "name": "Payment Service",
            "details": "Payment processing service",
            "current_status": "active",
        },
    ]


@pytest.fixture
def test_tasks_data():
    """Sample tasks data for testing."""
    return [
        {
            "title": "Implement OAuth",
            "description": "OAuth integration",
            "status": "todo",
            "project_id": 1,
        },
        {
            "title": "Add JWT validation",
            "description": "JWT token validation",
            "status": "todo",
            "project_id": 2,
        },
    ]


class TestResourceSharing:
    """Test M2M resource sharing functionality."""

    def test_resource_sharing_across_projects(self, client, db_session, test_projects_data):
        """Test that the same resource can be shared across multiple projects."""
        # Create two projects
        project_repo = ProjectRepository(db_session)
        project1 = project_repo.create(Project(**test_projects_data[0]))
        project2 = project_repo.create(Project(**test_projects_data[1]))
        db_session.commit()

        # Add the same GitHub repo to both projects
        shared_resource_uri = "https://github.com/owner/auth-repo"

        # Add to first project
        response1 = client.post(
            f"/api/projects/{project1.id}/resources",
            json={"resource_uri": shared_resource_uri, "description": "Authentication repository"},
        )
        assert response1.status_code == 200
        resource1_data = response1.json()

        # Add the same URI to second project
        response2 = client.post(
            f"/api/projects/{project2.id}/resources",
            json={"resource_uri": shared_resource_uri, "description": "Shared auth repo"},
        )
        assert response2.status_code == 200
        resource2_data = response2.json()

        # Should be the same resource (same ID)
        assert resource1_data["id"] == resource2_data["id"]
        assert resource1_data["resource_uri"] == shared_resource_uri
        assert resource2_data["resource_uri"] == shared_resource_uri

        # Both projects should list the resource
        proj1_resources = client.get(f"/api/projects/{project1.id}/resources").json()
        proj2_resources = client.get(f"/api/projects/{project2.id}/resources").json()

        assert len(proj1_resources) == 1
        assert len(proj2_resources) == 1
        assert proj1_resources[0]["id"] == proj2_resources[0]["id"]

    def test_resource_sharing_across_projects_and_tasks(
        self, client, db_session, test_projects_data, test_tasks_data
    ):
        """Test that resources can be shared between projects and tasks."""
        # Create projects and tasks
        project_repo = ProjectRepository(db_session)
        task_repo = TaskRepository(db_session)

        project = project_repo.create(Project(**test_projects_data[0]))
        db_session.flush()

        task_data = test_tasks_data[0].copy()
        task_data["project_id"] = project.id
        task = task_repo.create(Task(**task_data))
        db_session.commit()

        # Add same resource to project and task
        shared_resource_uri = "https://github.com/owner/shared-repo"

        # Add to project
        proj_response = client.post(
            f"/api/projects/{project.id}/resources",
            json={"resource_uri": shared_resource_uri, "description": "Shared repository"},
        )
        assert proj_response.status_code == 200
        proj_resource = proj_response.json()

        # Add same URI to task
        task_response = client.post(
            f"/api/tasks/{task.id}/resources",
            json={"resource_uri": shared_resource_uri, "description": "Same shared repo"},
        )
        assert task_response.status_code == 200
        task_resource = task_response.json()

        # Should be the same resource
        assert proj_resource["id"] == task_resource["id"]

    def test_cascade_deletion_with_shared_resources(self, client, db_session, test_projects_data):
        """Test cascade deletion: resource is deleted only when all links are removed."""
        # Create two projects
        project_repo = ProjectRepository(db_session)
        project1 = project_repo.create(Project(**test_projects_data[0]))
        project2 = project_repo.create(Project(**test_projects_data[1]))
        db_session.commit()

        # Add shared resource to both projects
        shared_resource_uri = "https://github.com/owner/shared-repo"

        response1 = client.post(
            f"/api/projects/{project1.id}/resources",
            json={"resource_uri": shared_resource_uri, "description": "Shared repository"},
        )
        resource_data = response1.json()
        resource_id = resource_data["id"]

        client.post(
            f"/api/projects/{project2.id}/resources",
            json={"resource_uri": shared_resource_uri, "description": "Same shared repo"},
        )

        # Verify resource exists in database
        resource_repo = ContextProviderResourceRepository(db_session)
        resource = resource_repo.get_by_id(resource_id)
        assert resource is not None

        # Remove from first project - resource should still exist
        delete_response1 = client.delete(f"/api/projects/{project1.id}/resources/{resource_id}")
        assert delete_response1.status_code == 200

        # Resource should still exist (linked to project2)
        resource = resource_repo.get_by_id(resource_id)
        assert resource is not None

        # Verify project2 still has the resource
        proj2_resources = client.get(f"/api/projects/{project2.id}/resources").json()
        assert len(proj2_resources) == 1

        # Remove from second project - resource should be deleted (cascade)
        delete_response2 = client.delete(f"/api/projects/{project2.id}/resources/{resource_id}")
        assert delete_response2.status_code == 200

        # Resource should now be deleted from database
        resource = resource_repo.get_by_id(resource_id)
        assert resource is None

    @pytest.mark.asyncio
    async def test_resource_service_find_or_create(self, db_session):
        """Test ResourceService find-or-create functionality."""
        resource_service = ResourceService(db_session)

        # Create first resource
        resource1 = await resource_service.find_or_create_resource(
            "https://github.com/owner/repo", "Test repository"
        )
        db_session.commit()

        # Try to create same URI again - should return existing
        resource2 = await resource_service.find_or_create_resource(
            "https://github.com/owner/repo", "Different description"
        )

        # Should be same resource
        assert resource1.id == resource2.id
        # Original description should be preserved
        assert resource1.description == "Test repository"

    def test_resource_usage_count(self, client, db_session, test_projects_data, test_tasks_data):
        """Test getting usage count for a shared resource."""
        # Create projects and task
        project_repo = ProjectRepository(db_session)
        task_repo = TaskRepository(db_session)

        project1 = project_repo.create(Project(**test_projects_data[0]))
        project2 = project_repo.create(Project(**test_projects_data[1]))
        db_session.flush()

        task_data = test_tasks_data[0].copy()
        task_data["project_id"] = project1.id
        task = task_repo.create(Task(**task_data))
        db_session.commit()

        # Add same resource to both projects and one task
        shared_resource_uri = "https://github.com/owner/popular-repo"

        # Add to project 1
        response = client.post(
            f"/api/projects/{project1.id}/resources",
            json={"resource_uri": shared_resource_uri, "description": "Popular repository"},
        )
        resource_id = response.json()["id"]

        # Add to project 2 (same resource)
        client.post(
            f"/api/projects/{project2.id}/resources", json={"resource_uri": shared_resource_uri}
        )

        # Add to task (same resource)
        client.post(f"/api/tasks/{task.id}/resources", json={"resource_uri": shared_resource_uri})

        # Test usage count via service
        resource_service = ResourceService(db_session)
        usage_count = resource_service.get_resource_usage_count(resource_id)
        assert usage_count == 3  # 2 projects + 1 task

        # Test getting projects and tasks for resource
        projects = resource_service.get_projects_for_resource(resource_id)
        tasks = resource_service.get_tasks_for_resource(resource_id)

        assert len(projects) == 2
        assert len(tasks) == 1
