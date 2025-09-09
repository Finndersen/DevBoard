"""Tests for tasks router."""

import pytest

from devboard.db.models import Project, Task
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
        # Create test project first
        project_repo = ProjectRepository(db_session)
        project = Project(
            name="Test Project",
            details="Test project details",
            current_status="active"
        )
        created_project = project_repo.create(project)
        db_session.commit()

        # Create test task
        test_task_data["project_id"] = created_project.id
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
        # Create test projects first
        project_repo = ProjectRepository(db_session)
        project1 = Project(name="Test Project 1", details="Test project 1", current_status="active")
        project2 = Project(name="Test Project 2", details="Test project 2", current_status="active")
        created_project1 = project_repo.create(project1)
        created_project2 = project_repo.create(project2)
        db_session.commit()

        # Create tasks for different projects
        task_repo = TaskRepository(db_session)
        task1 = Task(title="Task 1", description="Task 1", status="todo", project_id=created_project1.id)
        task2 = Task(title="Task 2", description="Task 2", status="todo", project_id=created_project2.id)
        task3 = Task(title="Task 3", description="Task 3", status="todo", project_id=created_project1.id)

        task_repo.create(task1)
        task_repo.create(task2)
        task_repo.create(task3)
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
        # Create test project first
        project_repo = ProjectRepository(db_session)
        project = Project(
            name="Test Project",
            details="Test project details",
            current_status="active"
        )
        created_project = project_repo.create(project)
        db_session.commit()

        # Update task data with actual project ID
        test_task_data["project_id"] = created_project.id

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
        # Create test task
        task_repo = TaskRepository(db_session)
        task = Task(**test_task_data)
        created_task = task_repo.create(task)
        db_session.commit()

        response = client.delete(f"/api/tasks/{created_task.id}/resources/999")
        assert response.status_code == 404
        assert "Resource not found or does not belong to this task" in response.json()["detail"]


class TestTaskPlanningAgentEndpoints:
    """Test task planning agent API endpoints."""

    @pytest.fixture
    def test_task_with_project(self, db_session):
        """Create a test task with project for planning agent tests."""
        # Create project
        project_repo = ProjectRepository(db_session)
        project = Project(
            name="Test Project",
            details="Test project details",
            current_status="active"
        )
        created_project = project_repo.create(project)

        # Create task
        task_repo = TaskRepository(db_session)
        task = Task(
            title="Test Task",
            description="Initial task description",
            status="Designing",
            project_id=created_project.id
        )
        created_task = task_repo.create(task)
        db_session.commit()

        return created_task

    def test_get_task_messages_empty(self, client, test_task_with_project):
        """Test getting task messages when none exist."""
        task = test_task_with_project

        response = client.get(f"/api/tasks/{task.id}/messages")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_task_messages_with_data(self, client, db_session, test_task_with_project):
        """Test getting task messages with existing conversation."""
        from devboard.db.models import TaskConversationMessage

        task = test_task_with_project

        # Add some conversation messages
        messages_data = [
            {"role": "user", "content": "Help me design this task"},
            {"role": "assistant", "content": "I'll help you create a specification",
             "tool_data": {"task_specification_edits": [{"find": "old", "replace": "new"}]}},
            {"role": "user", "content": "Add more details please"}
        ]

        for msg_data in messages_data:
            message = TaskConversationMessage(task_id=task.id, **msg_data)
            db_session.add(message)
        db_session.commit()

        response = client.get(f"/api/tasks/{task.id}/messages")
        assert response.status_code == 200

        messages = response.json()
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["tool_data"] is not None
        assert "task_specification_edits" in messages[1]["tool_data"]

    def test_get_task_messages_task_not_found(self, client):
        """Test getting messages for non-existent task."""
        response = client.get("/api/tasks/999/messages")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_apply_document_edits_specification_only(self, client, db_session, test_task_with_project):
        """Test applying edits to task specification only."""
        from devboard.db.models import TaskConversationMessage

        task = test_task_with_project

        # Create a message with edits
        message = TaskConversationMessage(
            task_id=task.id,
            role="assistant",
            content="Updated specification",
            tool_data={"task_specification_edits": [{"find": "old", "replace": "new"}]}
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Apply edits request
        edit_request = {
            "message_id": message.id,
            "task_specification_edits": [
                {"find": "Initial task description", "replace": "Updated task specification with new details"}
            ]
        }

        response = client.post(f"/api/tasks/{task.id}/apply-edits", json=edit_request)
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["description"] == "Updated task specification with new details"
        assert updated_task["implementation_plan"] is None  # Should remain unchanged

    def test_apply_document_edits_both_documents(self, client, db_session, test_task_with_project):
        """Test applying edits to both specification and implementation plan."""
        from devboard.db.models import TaskConversationMessage

        task = test_task_with_project
        # Set initial implementation plan
        task.implementation_plan = "Initial implementation plan"
        db_session.commit()

        # Create message
        message = TaskConversationMessage(
            task_id=task.id,
            role="assistant",
            content="Updated both documents"
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Apply edits to both documents
        edit_request = {
            "message_id": message.id,
            "task_specification_edits": [
                {"find": "Initial task description", "replace": "Enhanced task specification"}
            ],
            "task_implementation_plan_edits": [
                {"find": "Initial implementation plan", "replace": "Detailed implementation plan with steps"}
            ]
        }

        response = client.post(f"/api/tasks/{task.id}/apply-edits", json=edit_request)
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["description"] == "Enhanced task specification"
        assert updated_task["implementation_plan"] == "Detailed implementation plan with steps"

    def test_apply_document_edits_invalid_message(self, client, test_task_with_project):
        """Test applying edits with invalid message ID."""
        task = test_task_with_project

        edit_request = {
            "message_id": 999,
            "task_specification_edits": [{"find": "old", "replace": "new"}]
        }

        response = client.post(f"/api/tasks/{task.id}/apply-edits", json=edit_request)
        assert response.status_code == 404
        assert response.json()["detail"] == "Message not found"

    def test_apply_document_edits_edit_failure(self, client, db_session, test_task_with_project):
        """Test applying edits when edit operation fails."""
        from devboard.db.models import TaskConversationMessage

        task = test_task_with_project

        # Create message
        message = TaskConversationMessage(
            task_id=task.id,
            role="assistant",
            content="Attempted update"
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Try to edit text that doesn't exist
        edit_request = {
            "message_id": message.id,
            "task_specification_edits": [
                {"find": "nonexistent text", "replace": "new text"}
            ]
        }

        response = client.post(f"/api/tasks/{task.id}/apply-edits", json=edit_request)
        assert response.status_code == 400
        assert "Edit application failed" in response.json()["detail"]
        assert "Text to find not found" in response.json()["detail"]

    def test_transition_task_state_success(self, client, test_task_with_project):
        """Test successful task state transition."""
        task = test_task_with_project
        assert task.status == "Designing"

        transition_request = {"new_state": "Planning"}

        response = client.post(f"/api/tasks/{task.id}/state-transition", json=transition_request)
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["status"] == "Planning"

    def test_transition_task_state_invalid_state(self, client, test_task_with_project):
        """Test task state transition with invalid state."""
        task = test_task_with_project

        transition_request = {"new_state": "InvalidState"}

        response = client.post(f"/api/tasks/{task.id}/state-transition", json=transition_request)
        assert response.status_code == 400
        assert "Invalid state" in response.json()["detail"]

    def test_transition_task_state_task_not_found(self, client):
        """Test state transition for non-existent task."""
        transition_request = {"new_state": "Planning"}

        response = client.post("/api/tasks/999/state-transition", json=transition_request)
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"
