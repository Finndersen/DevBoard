"""Tests for tasks router."""

import pytest

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.roles.types import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.codebase import Codebase
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import (
    CodebaseRepository,
    ContextProviderResourceRepository,
    ConversationRepository,
    DocumentRepository,
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

    def test_create_task(self, client, db_session, test_task_data):
        """Test creating a new task."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )
        db_session.commit()

        # Use the nested schema structure (no project_id in body)
        api_task_data = {
            "title": test_task_data["title"],
            "status": test_task_data["status"].value,  # Convert enum to string
        }

        # POST to the new nested endpoint
        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == test_task_data["title"]
        assert task_data["status"] == test_task_data["status"].value
        assert task_data["project_id"] == created_project.id
        assert "id" in task_data
        assert "conversation_id" in task_data
        assert isinstance(task_data["conversation_id"], int)

    def test_get_task_success(self, client, db_session, test_task_data):
        """Test getting a specific task."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
        )
        db_session.commit()

        # Create conversation for task (required by get_task endpoint)
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
        )

        # Create conversation for task
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
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

    def test_update_task_codebase_assignment(self, client, db_session, test_task_data):
        """Test updating task codebase assignment."""
        # Create test project and codebase
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        codebase_repo = CodebaseRepository(db_session)

        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create a test codebase
        codebase = Codebase(
            name="Test Codebase",
            description="A test codebase",
            local_path="/path/to/test/codebase",
            repository_url="https://github.com/test/repo",
        )
        created_codebase = codebase_repo.create(codebase)

        # Create test task without codebase
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
            codebase_id=None,  # Start without codebase
        )

        # Create conversation for task
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        db_session.commit()

        # Update task to assign codebase
        update_data = {"codebase_id": created_codebase.id}
        response = client.patch(f"/api/tasks/{created_task.id}", json=update_data)
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["codebase_id"] == created_codebase.id

        # Verify the update persisted
        get_response = client.get(f"/api/tasks/{created_task.id}")
        assert get_response.status_code == 200
        assert get_response.json()["codebase_id"] == created_codebase.id

    def test_update_task_remove_codebase(self, client, db_session, test_task_data):
        """Test removing codebase assignment from a task."""
        # Create test project and codebase
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        codebase_repo = CodebaseRepository(db_session)

        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create a test codebase
        codebase = Codebase(
            name="Test Codebase",
            description="A test codebase",
            local_path="/path/to/test/codebase",
            repository_url="https://github.com/test/repo",
        )
        created_codebase = codebase_repo.create(codebase)

        # Create test task with codebase
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
            codebase_id=created_codebase.id,  # Start with codebase
        )

        # Create conversation for task
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        db_session.commit()

        # Update task to remove codebase
        update_data = {"codebase_id": None}
        response = client.patch(f"/api/tasks/{created_task.id}", json=update_data)
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["codebase_id"] is None

        # Verify the update persisted
        get_response = client.get(f"/api/tasks/{created_task.id}")
        assert get_response.status_code == 200
        assert get_response.json()["codebase_id"] is None


class TestTaskResourcesRouter:
    """Test task resource endpoints."""

    def test_list_task_resources_empty(self, client, db_session, test_task_data):
        """Test listing task resources when none exist."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
        )
        db_session.commit()

        response = client.get(f"/api/tasks/{created_task.id}/resources")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_task_resources_with_data(self, client, db_session, test_task_data, test_resource_data):
        """Test listing task resources with existing data."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
        )
        db_session.commit()

        response = client.delete(f"/api/tasks/{created_task.id}/resources/999")
        assert response.status_code == 404
        assert "Resource not found or does not belong to this task" in response.json()["detail"]


class TestTaskStateTransition:
    """Test task state transition API endpoints."""

    @pytest.fixture
    def test_task_with_project(self, db_session):
        """Create a test task with project for state transition tests."""
        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository with specification content
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "# Task Specification\n\nTest content")
        # Don't create implementation_plan yet - it will be created during transition
        created_task = task_repo.create(
            project_id=created_project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
            implementation_plan=None,
        )

        # Create conversation for task
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        db_session.commit()

        return created_task

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

    def test_transition_defining_to_planning_without_spec(self, client, db_session):
        """Test transitioning from DEFINING to PLANNING without specification content fails."""
        # Create task with empty specification
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(name="Test Project", description="A test project", specification=spec_doc)

        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")  # Empty spec
        created_task = task_repo.create(
            project_id=created_project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
            implementation_plan=None,
        )

        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        db_session.commit()

        # Try to transition without spec content
        response = client.post(
            f"/api/tasks/{created_task.id}/state-transition",
            json={"new_state": TaskStatus.PLANNING.value},
        )
        assert response.status_code == 400
        assert "specification content" in response.json()["detail"].lower()

    def test_transition_defining_to_planning_creates_implementation_plan(self, client, db_session):
        """Test transitioning from DEFINING to PLANNING creates implementation_plan document."""
        # Create task with specification content
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(name="Test Project", description="A test project", specification=spec_doc)

        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "# Task Specification\n\nTest content")
        created_task = task_repo.create(
            project_id=created_project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
            implementation_plan=None,  # No plan initially
        )

        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        db_session.commit()

        # Transition to PLANNING
        response = client.post(
            f"/api/tasks/{created_task.id}/state-transition",
            json={"new_state": TaskStatus.PLANNING.value},
        )
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["status"] == TaskStatus.PLANNING.value
        assert updated_task["implementation_plan"] is not None
        assert updated_task["implementation_plan"]["document_type"] == "task_implementation_plan"

    def test_transition_creates_new_conversation_with_correct_role(self, client, db_session):
        """Test that state transition updates conversation role when transitioning to PLANNING with same engine."""
        # Create task with specification content
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(name="Test Project", description="A test project", specification=spec_doc)

        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "# Task Specification\n\nTest content")
        created_task = task_repo.create(
            project_id=created_project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
            implementation_plan=None,
        )

        conversation_repo = ConversationRepository(db_session)
        initial_conversation = conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        db_session.commit()
        initial_conversation_id = initial_conversation.id

        # Transition to PLANNING
        response = client.post(
            f"/api/tasks/{created_task.id}/state-transition",
            json={"new_state": TaskStatus.PLANNING.value},
        )
        assert response.status_code == 200

        updated_task = response.json()
        conversation_id = updated_task["conversation_id"]

        # Verify conversation was reused (same ID) since both roles use INTERNAL engine
        assert conversation_id == initial_conversation_id

        # Verify conversation has updated role
        conversation = conversation_repo.get_by_id(conversation_id)
        assert conversation is not None
        assert conversation.agent_role == AgentRoleType.TASK_PLANNING
        assert conversation.is_active is True
        assert conversation.archived_at is None  # Should not be archived

    def test_transition_planning_to_implementing_without_plan(self, client, db_session):
        """Test transitioning from PLANNING to IMPLEMENTING without implementation plan fails."""
        # Create task in PLANNING state with empty plan
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(name="Test Project", description="A test project", specification=spec_doc)

        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "# Task Specification")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")  # Empty plan
        created_task = task_repo.create(
            project_id=created_project.id,
            title="Test Task",
            status=TaskStatus.PLANNING,
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
        )

        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_PLANNING,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        db_session.commit()

        # Try to transition without plan content
        response = client.post(
            f"/api/tasks/{created_task.id}/state-transition",
            json={"new_state": TaskStatus.IMPLEMENTING.value},
        )
        assert response.status_code == 400
        assert "implementation plan" in response.json()["detail"].lower()

    def test_transition_defining_to_planning_reuses_conversation_same_engine(self, client, db_session):
        """Test transitioning from DEFINING to PLANNING reuses conversation when engine is same."""
        # Create task with specification content
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(name="Test Project", description="A test project", specification=spec_doc)

        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "# Task Specification\n\nTest content")
        created_task = task_repo.create(
            project_id=created_project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
            implementation_plan=None,
        )

        # Create conversation with INTERNAL engine (both roles use same engine by default)
        conversation_repo = ConversationRepository(db_session)
        initial_conversation = conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        db_session.commit()
        initial_conversation_id = initial_conversation.id

        # Transition to PLANNING
        response = client.post(
            f"/api/tasks/{created_task.id}/state-transition",
            json={"new_state": TaskStatus.PLANNING.value},
        )
        assert response.status_code == 200

        updated_task = response.json()
        conversation_id = updated_task["conversation_id"]

        # Verify conversation was reused (same ID)
        assert conversation_id == initial_conversation_id

        # Verify conversation was updated with new role
        conversation = conversation_repo.get_by_id(conversation_id)
        assert conversation is not None
        assert conversation.agent_role == AgentRoleType.TASK_PLANNING
        assert conversation.is_active is True
        assert conversation.archived_at is None  # Should not be archived

    def test_transition_defining_to_planning_creates_new_conversation_different_engine(self, client, db_session):
        """Test transitioning from DEFINING to PLANNING creates new conversation when engine changes."""
        # Create task with specification content
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(name="Test Project", description="A test project", specification=spec_doc)

        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "# Task Specification\n\nTest content")
        created_task = task_repo.create(
            project_id=created_project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
            implementation_plan=None,
        )

        # Create conversation with CLAUDE_CODE engine
        # Note: In real scenario, the new role would use different engine from config
        conversation_repo = ConversationRepository(db_session)
        initial_conversation = conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.CLAUDE_CODE,
            model_id="anthropic:claude-sonnet-4",
        )
        db_session.commit()
        initial_conversation_id = initial_conversation.id

        # Transition to PLANNING (assuming PLANNING uses INTERNAL engine, different from CLAUDE_CODE)
        response = client.post(
            f"/api/tasks/{created_task.id}/state-transition",
            json={"new_state": TaskStatus.PLANNING.value},
        )
        assert response.status_code == 200

        updated_task = response.json()
        new_conversation_id = updated_task["conversation_id"]

        # Verify new conversation was created (different ID)
        assert new_conversation_id != initial_conversation_id

        # Verify new conversation has correct role and engine
        new_conversation = conversation_repo.get_by_id(new_conversation_id)
        assert new_conversation is not None
        assert new_conversation.agent_role == AgentRoleType.TASK_PLANNING
        assert new_conversation.is_active is True

        # Verify old conversation was archived
        old_conversation = conversation_repo.get_by_id(initial_conversation_id)
        assert old_conversation is not None
        assert old_conversation.is_active is False
        assert old_conversation.archived_at is not None
