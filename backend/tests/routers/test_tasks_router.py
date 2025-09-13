"""Tests for tasks router."""

import pytest

from devboard.db.models.task import TaskStatus
from devboard.db.repositories import (
    ContextProviderResourceRepository,
    ProjectRepository,
    TaskRepository,
)


@pytest.fixture
def test_task_data():
    """Sample task data for testing."""
    return {
        "title": "Test Task",
        "status": TaskStatus.DEFINING,
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
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
        )
        db_session.commit()

        response = client.get("/api/tasks/")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1
        assert tasks[0]["title"] == test_task_data["title"]
        assert tasks[0]["id"] == created_task.id

    def test_list_tasks_filtered_by_project(self, client, db_session):
        """Test listing tasks filtered by project ID."""
        # Create test projects using repository
        project_repo = ProjectRepository(db_session)
        created_project1 = project_repo.create(name="Test Project 1", description="A test project for development")
        created_project2 = project_repo.create(name="Test Project 2", description="A test project for development")

        # Create tasks for different projects using repository
        task_repo = TaskRepository(db_session)
        task_repo.create(project_id=created_project1.id, title="Task 1", status=TaskStatus.DEFINING)
        task_repo.create(project_id=created_project2.id, title="Task 2", status=TaskStatus.DEFINING)
        task_repo.create(project_id=created_project1.id, title="Task 3", status=TaskStatus.DEFINING)
        db_session.commit()

        # Test filtering by project 1
        response = client.get(f"/api/tasks/?project_id={created_project1.id}")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 2
        assert all(task["project_id"] == created_project1.id for task in tasks)

        # Test filtering by project 2
        response = client.get(f"/api/tasks/?project_id={created_project2.id}")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1
        assert tasks[0]["project_id"] == created_project2.id

    def test_create_task(self, client, db_session, test_task_data):
        """Test creating a new task."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")
        db_session.commit()

        # Update task data with actual project ID
        test_task_data["project_id"] = created_project.id
        # Use the schema structure
        api_task_data = {
            "title": test_task_data["title"],
            "status": test_task_data["status"].value,  # Convert enum to string
            "project_id": test_task_data["project_id"],
        }

        response = client.post("/api/tasks/", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == test_task_data["title"]
        assert task_data["status"] == test_task_data["status"].value
        assert task_data["project_id"] == test_task_data["project_id"]
        assert "id" in task_data

    def test_get_task_success(self, client, db_session, test_task_data):
        """Test getting a specific task."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
        )
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
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
        )
        db_session.commit()

        update_data = {"title": "Updated Task Title", "status": TaskStatus.IMPLEMENTING.value}
        response = client.patch(f"/api/tasks/{created_task.id}", json=update_data)
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["title"] == "Updated Task Title"
        assert updated_task["status"] == TaskStatus.IMPLEMENTING.value
        assert updated_task["project_id"] == created_project.id  # Unchanged

    def test_update_task_not_found(self, client):
        """Test updating a non-existent task."""

        update_data = {"title": "Updated Title"}
        response = client.patch("/api/tasks/999", json=update_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_delete_task_success(self, client, db_session, test_task_data):
        """Test deleting a task."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
        )
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
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
        )
        db_session.commit()

        response = client.get(f"/api/tasks/{created_task.id}/resources")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_task_resources_with_data(self, client, db_session, test_task_data, test_resource_data):
        """Test listing task resources with existing data."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
        )
        db_session.commit()

        # Create test resource
        resource_repo = ContextProviderResourceRepository(db_session)
        resource = resource_repo.create_task_resource(
            task_id=created_task.id,
            resource_uri=test_resource_data["resource_uri"],
            provider_name="github",
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
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
        )
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

    def test_delete_task_resource_success(self, client, db_session, test_task_data, test_resource_data):
        """Test deleting a task resource."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
        )
        db_session.commit()

        # Create test resource
        resource_repo = ContextProviderResourceRepository(db_session)
        resource = resource_repo.create_task_resource(
            task_id=created_task.id,
            resource_uri=test_resource_data["resource_uri"],
            provider_name="github",
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
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
        )
        db_session.commit()

        response = client.delete(f"/api/tasks/{created_task.id}/resources/999")
        assert response.status_code == 404
        assert "Resource not found or does not belong to this task" in response.json()["detail"]


class TestTaskPlanningAgentEndpoints:
    """Test task planning agent API endpoints."""

    @pytest.fixture
    def test_task_with_project(self, db_session):
        """Create a test task with project for planning agent tests."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(project_id=created_project.id, title="Test Task", status=TaskStatus.DEFINING)
        db_session.commit()

        return created_task

    @pytest.mark.skip(reason="Message sending requires actual AI agent - integration test only")
    def test_send_task_conversation_message(self, client, test_task_with_project):
        """Test sending a message to the task planning agent."""
        task = test_task_with_project

        message_request = {"message": "Help me create a task specification for user authentication."}

        response = client.post(f"/api/tasks/{task.id}/conversation", json=message_request)
        assert response.status_code == 200

        conversation_response = response.json()
        assert "messages" in conversation_response
        assert "pending_approvals" in conversation_response
        assert "conversation_complete" in conversation_response

    def test_send_task_conversation_message_task_not_found(self, client):
        """Test sending message to non-existent task."""
        message_request = {"query": "Test message"}

        response = client.post("/api/tasks/999/agent/messages", json=message_request)
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    @pytest.mark.skip(reason="Tool approval requires pending tools from AI agent - integration test only")
    def test_approve_task_tools(self, client, test_task_with_project):
        """Test approving tool calls from the task planning agent."""
        task = test_task_with_project

        approval_request = {
            "approvals": {"test_call_1": {"approved": True, "feedback": "Looks good, proceed with the edit"}}
        }

        response = client.post(f"/api/tasks/{task.id}/conversation/approve-tools", json=approval_request)
        assert response.status_code == 200

        conversation_response = response.json()
        assert "messages" in conversation_response
        assert "pending_approvals" in conversation_response
        assert conversation_response["conversation_complete"] is True

    def test_approve_task_tools_task_not_found(self, client):
        """Test tool approval for non-existent task."""
        approval_request = {"approvals": {"test_call_1": {"approved": True}}}

        response = client.post("/api/tasks/999/agent/approve-tools", json=approval_request)
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_transition_task_state_success(self, client, test_task_with_project):
        """Test successful task state transition."""
        task = test_task_with_project
        assert task.status == TaskStatus.DEFINING

        transition_request = {"new_state": TaskStatus.PLANNING.value}

        response = client.post(f"/api/tasks/{task.id}/state-transition", json=transition_request)
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["status"] == TaskStatus.PLANNING.value

    def test_transition_task_state_invalid_state(self, client, test_task_with_project):
        """Test task state transition with invalid state."""
        task = test_task_with_project

        transition_request = {"new_state": "InvalidState"}

        response = client.post(f"/api/tasks/{task.id}/state-transition", json=transition_request)
        assert response.status_code == 422  # Unprocessable Entity for validation errors
        assert response.json()["detail"]  # Should have validation error details

    def test_transition_task_state_task_not_found(self, client):
        """Test state transition for non-existent task."""
        transition_request = {"new_state": "planning"}  # Use correct enum value

        response = client.post("/api/tasks/999/state-transition", json=transition_request)
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"
