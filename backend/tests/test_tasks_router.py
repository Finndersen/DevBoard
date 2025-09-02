"""Tests for tasks router."""

import pytest

from devboard.db.models import Task
from devboard.db.repositories import ContextProviderResourceRepository, TaskRepository


@pytest.fixture
def test_task_data():
    """Sample task data for testing."""
    return {
        "title": "Test Task",
        "description": "Test task description",
        "status": "todo",
        "project_id": 1,
    }


@pytest.fixture
def test_resource_data():
    """Sample context provider resource data for testing."""
    return {
        "resource_uri": "https://github.com/owner/repo",
        "description": "Test GitHub repository",
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


class TestTaskResourcesRouter:
    """Test task resource endpoints."""

    def test_list_task_resources_empty(self, client, db_session, test_task_data):
        """Test listing task resources when none exist."""
        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        response = client.get(f"/api/tasks/{created_task.id}/resources")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_task_resources_with_data(
        self, client, db_session, test_task_data, test_resource_data
    ):
        """Test listing task resources with existing data."""
        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        # Create test resource
        resource_repo = ContextProviderResourceRepository(db_session)
        resource = resource_repo.create_task_resource(
            task_id=created_task.id,
            resource_uri=test_resource_data["resource_uri"],
            description=test_resource_data["description"],
        )
        db_session.commit()

        response = client.get(f"/api/tasks/{created_task.id}/resources")
        assert response.status_code == 200

        resources = response.json()
        assert len(resources) == 1
        assert resources[0]["resource_uri"] == test_resource_data["resource_uri"]
        assert resources[0]["description"] == test_resource_data["description"]
        assert resources[0]["id"] == resource.id

    def test_list_task_resources_task_not_found(self, client):
        """Test listing resources for non-existent task."""
        response = client.get("/api/tasks/999/resources")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_create_task_resource(self, client, db_session, test_task_data, test_resource_data):
        """Test creating a new task resource."""
        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        response = client.post(f"/api/tasks/{created_task.id}/resources", json=test_resource_data)
        assert response.status_code == 200

        resource_data = response.json()
        assert resource_data["resource_uri"] == test_resource_data["resource_uri"]
        assert resource_data["description"] == test_resource_data["description"]
        assert "id" in resource_data

    def test_create_task_resource_task_not_found(self, client, test_resource_data):
        """Test creating a resource for non-existent task."""
        response = client.post("/api/tasks/999/resources", json=test_resource_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_delete_task_resource_success(
        self, client, db_session, test_task_data, test_resource_data
    ):
        """Test deleting a task resource."""
        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        # Create test resource
        resource_repo = ContextProviderResourceRepository(db_session)
        resource = resource_repo.create_task_resource(
            task_id=created_task.id,
            resource_uri=test_resource_data["resource_uri"],
            description=test_resource_data["description"],
        )
        db_session.commit()

        response = client.delete(f"/api/tasks/{created_task.id}/resources/{resource.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Resource deleted successfully"

    def test_delete_task_resource_task_not_found(self, client):
        """Test deleting a resource for non-existent task."""
        response = client.delete("/api/tasks/999/resources/1")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_delete_task_resource_not_found(self, client, db_session, test_task_data):
        """Test deleting a non-existent task resource."""
        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        response = client.delete(f"/api/tasks/{created_task.id}/resources/999")
        assert response.status_code == 404
        assert "Resource not found or does not belong to this task" in response.json()["detail"]
