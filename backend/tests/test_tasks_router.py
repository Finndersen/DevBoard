"""Tests for tasks router."""

import pytest
from fastapi.testclient import TestClient

from devboard.db.models import Task
from devboard.main import app
from devboard.repositories.task import TaskRepository


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
def test_task_data():
    """Sample task data for testing."""
    return {
        "title": "Test Task",
        "description": "Test task description",
        "status": "todo",
        "project_id": 1,
    }


class TestTasksRouter:
    """Test tasks router endpoints."""

    def test_list_tasks_empty(self, client):
        """Test listing tasks when none exist."""
        response = client.get("/api/tasks/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_tasks_with_data(self, client, db_session, test_task_data):
        """Test listing tasks with existing data."""
        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        response = client.get("/api/tasks/")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == test_task_data["title"]
        assert tasks[0]["id"] == created_task.id

    def test_list_tasks_filtered_by_project(self, client, db_session):
        """Test listing tasks filtered by project ID."""

        # Create tasks for different projects
        task_repo = TaskRepository(db_session)
        task1 = Task(title="Task 1", description="Task 1", status="todo", project_id=1)
        task2 = Task(title="Task 2", description="Task 2", status="todo", project_id=2)
        task3 = Task(title="Task 3", description="Task 3", status="todo", project_id=1)

        task_repo.create(task1)
        task_repo.create(task2)
        task_repo.create(task3)
        db_session.commit()

        # Test filtering by project 1
        response = client.get("/api/tasks/?project_id=1")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 2
        assert all(task["project_id"] == 1 for task in tasks)

        # Test filtering by project 2
        response = client.get("/api/tasks/?project_id=2")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1
        assert tasks[0]["project_id"] == 2

    def test_create_task(self, client, db_session, test_task_data):
        """Test creating a new task."""

        response = client.post("/api/tasks/", json=test_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == test_task_data["title"]
        assert task_data["description"] == test_task_data["description"]
        assert task_data["status"] == test_task_data["status"]
        assert task_data["project_id"] == test_task_data["project_id"]
        assert "id" in task_data

    def test_get_task_success(self, client, db_session, test_task_data):
        """Test getting a specific task."""

        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        response = client.get(f"/api/tasks/{created_task.id}")
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == test_task_data["title"]
        assert task_data["id"] == created_task.id

    def test_get_task_not_found(self, client):
        """Test getting a non-existent task."""

        response = client.get("/api/tasks/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_update_task_success(self, client, db_session, test_task_data):
        """Test updating a task."""

        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        update_data = {"title": "Updated Task Title", "status": "in_progress"}
        response = client.patch(f"/api/tasks/{created_task.id}", json=update_data)
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["title"] == "Updated Task Title"
        assert updated_task["status"] == "in_progress"
        assert updated_task["description"] == test_task_data["description"]  # Unchanged
        assert updated_task["project_id"] == test_task_data["project_id"]  # Unchanged

    def test_update_task_not_found(self, client):
        """Test updating a non-existent task."""

        update_data = {"title": "Updated Title"}
        response = client.patch("/api/tasks/999", json=update_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_delete_task_success(self, client, db_session, test_task_data):
        """Test deleting a task."""

        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        response = client.delete(f"/api/tasks/{created_task.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Task deleted successfully"

        # Verify task is deleted
        get_response = client.get(f"/api/tasks/{created_task.id}")
        assert get_response.status_code == 404

    def test_delete_task_not_found(self, client):
        """Test deleting a non-existent task."""

        response = client.delete("/api/tasks/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"
