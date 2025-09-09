"""Tests for projects router."""

import pytest

from devboard.db.models import Project, Task
from devboard.db.repositories import (
    ContextProviderResourceRepository,
    ProjectRepository,
    TaskRepository,
)


@pytest.fixture
def test_project_data():
    """Sample project data for testing."""
    return {"name": "Test Project", "details": "Test project details", "current_status": "active"}


@pytest.fixture
def test_resource_data():
    """Sample context provider resource data for testing."""
    return {
        "resource_uri": "https://github.com/owner/repo",
        "description": "Test GitHub repository",
    }


@pytest.fixture
def test_task_data():
    """Sample task data for testing (without project_id)."""
    return {
        "title": "Test Task",
        "description": "Test task description",
        "status": "Pending",
    }


class TestProjectsRouter:
    """Test projects router endpoints."""

    def test_list_projects_empty(self, client):
        """Test listing projects when none exist."""
        response = client.get("/api/projects/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_projects_with_data(self, client, db_session, test_project_data):
        """Test listing projects with existing data."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        response = client.get("/api/projects/")
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) == 1
        assert projects[0]["name"] == test_project_data["name"]
        assert projects[0]["id"] == created_project.id

    def test_create_project(self, client, test_project_data):
        """Test creating a new project."""
        response = client.post("/api/projects/", json=test_project_data)
        assert response.status_code == 200

        project_data = response.json()
        assert project_data["name"] == test_project_data["name"]
        assert project_data["details"] == test_project_data["details"]
        assert project_data["current_status"] == test_project_data["current_status"]
        assert "id" in project_data

    def test_get_project_success(self, client, db_session, test_project_data):
        """Test getting a specific project."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        response = client.get(f"/api/projects/{created_project.id}")
        assert response.status_code == 200

        project_data = response.json()
        assert project_data["name"] == test_project_data["name"]
        assert project_data["id"] == created_project.id

    def test_get_project_not_found(self, client):
        """Test getting a non-existent project."""
        response = client.get("/api/projects/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

    def test_update_project_success(self, client, db_session, test_project_data):
        """Test updating a project."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        update_data = {"name": "Updated Project Name"}
        response = client.patch(f"/api/projects/{created_project.id}", json=update_data)
        assert response.status_code == 200

        updated_project = response.json()
        assert updated_project["name"] == "Updated Project Name"
        assert updated_project["details"] == test_project_data["details"]  # Unchanged

    def test_update_project_not_found(self, client):
        """Test updating a non-existent project."""
        update_data = {"name": "Updated Name"}
        response = client.patch("/api/projects/999", json=update_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

    def test_delete_project_success(self, client, db_session, test_project_data):
        """Test deleting a project."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        response = client.delete(f"/api/projects/{created_project.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Project deleted successfully"

        # Verify project is deleted
        get_response = client.get(f"/api/projects/{created_project.id}")
        assert get_response.status_code == 404

    def test_delete_project_not_found(self, client):
        """Test deleting a non-existent project."""
        response = client.delete("/api/projects/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"


class TestProjectResourcesRouter:
    """Test project resource endpoints."""

    def test_list_project_resources_empty(self, client, db_session, test_project_data):
        """Test listing project resources when none exist."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        response = client.get(f"/api/projects/{created_project.id}/resources")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_project_resources_with_data(
        self, client, db_session, test_project_data, test_resource_data
    ):
        """Test listing project resources with existing data."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        # Create test resource
        resource_repo = ContextProviderResourceRepository(db_session)
        resource = resource_repo.create_project_resource(
            project_id=created_project.id,
            resource_uri=test_resource_data["resource_uri"],
            provider_name="github",
            description=test_resource_data["description"],
        )
        db_session.commit()

        response = client.get(f"/api/projects/{created_project.id}/resources")
        assert response.status_code == 200

        resources = response.json()
        assert len(resources) == 1
        assert resources[0]["resource_uri"] == test_resource_data["resource_uri"]
        assert resources[0]["description"] == test_resource_data["description"]
        assert resources[0]["id"] == resource.id

    def test_list_project_resources_project_not_found(self, client):
        """Test listing resources for non-existent project."""
        response = client.get("/api/projects/999/resources")
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

    def test_create_project_resource(
        self, client, db_session, test_project_data, test_resource_data
    ):
        """Test creating a new project resource."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        response = client.post(
            f"/api/projects/{created_project.id}/resources", json=test_resource_data
        )
        assert response.status_code == 200

        resource_data = response.json()
        assert resource_data["resource_uri"] == test_resource_data["resource_uri"]
        assert resource_data["description"] == test_resource_data["description"]
        assert "id" in resource_data

    def test_create_project_resource_project_not_found(self, client, test_resource_data):
        """Test creating a resource for non-existent project."""
        response = client.post("/api/projects/999/resources", json=test_resource_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

    def test_delete_project_resource_success(
        self, client, db_session, test_project_data, test_resource_data
    ):
        """Test deleting a project resource."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        # Create test resource
        resource_repo = ContextProviderResourceRepository(db_session)
        resource = resource_repo.create_project_resource(
            project_id=created_project.id,
            resource_uri=test_resource_data["resource_uri"],
            provider_name="github",
            description=test_resource_data["description"],
        )
        db_session.commit()

        response = client.delete(f"/api/projects/{created_project.id}/resources/{resource.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Resource deleted successfully"

    def test_delete_project_resource_project_not_found(self, client):
        """Test deleting a resource for non-existent project."""
        response = client.delete("/api/projects/999/resources/1")
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

    def test_delete_project_resource_not_found(self, client, db_session, test_project_data):
        """Test deleting a non-existent project resource."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        response = client.delete(f"/api/projects/{created_project.id}/resources/999")
        assert response.status_code == 404
        assert "Resource not found or does not belong to this project" in response.json()["detail"]


class TestProjectTasksRouter:
    """Test project tasks router endpoints."""

    def test_list_project_tasks_empty(self, client, db_session, test_project_data):
        """Test listing project tasks when none exist."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        response = client.get(f"/api/projects/{created_project.id}/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_project_tasks_with_data(self, client, db_session, test_project_data, test_task_data):
        """Test listing project tasks with existing data."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        project = Project(**test_project_data)
        created_project = project_repo.create(project)
        db_session.commit()

        # Create test tasks
        task_repo = TaskRepository(db_session)
        task1_data = {**test_task_data, "project_id": created_project.id, "title": "Task 1"}
        task2_data = {**test_task_data, "project_id": created_project.id, "title": "Task 2"}
        task1 = Task(**task1_data)
        task2 = Task(**task2_data)
        task_repo.create(task1)
        task_repo.create(task2)
        db_session.commit()

        response = client.get(f"/api/projects/{created_project.id}/tasks")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 2
        assert tasks[0]["title"] in ["Task 1", "Task 2"]
        assert tasks[1]["title"] in ["Task 1", "Task 2"]

    def test_list_project_tasks_project_not_found(self, client):
        """Test listing tasks for non-existent project."""
        response = client.get("/api/projects/999/tasks")
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

