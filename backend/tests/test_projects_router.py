"""Tests for projects router."""

import pytest
from fastapi.testclient import TestClient

from devboard.db.models import Project
from devboard.main import app
from devboard.repositories.project import ProjectRepository


@pytest.fixture
def client(db_session):
    """FastAPI test client with database setup."""
    from devboard.db.database import get_db

    def override_get_db():
        return db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_project_data():
    """Sample project data for testing."""
    return {"name": "Test Project", "details": "Test project details", "current_status": "active"}


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
