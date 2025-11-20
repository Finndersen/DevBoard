"""Tests for projects router."""

import pytest

# from devboard.api.dependencies.agents import get_project_agent  # Removed in refactor
from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.codebase import Codebase
from devboard.db.models.document import DocumentType
from devboard.db.repositories import (
    CodebaseRepository,
    ContextProviderResourceRepository,
    ConversationRepository,
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)


@pytest.fixture
def test_project_data():
    """Sample project data for testing."""
    return {"name": "Test Project", "description": "A test project for development"}


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
        "status": "defining",
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
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
        assert project_data["description"] == test_project_data["description"]
        assert "id" in project_data

    def test_get_project_success(self, client, db_session, test_project_data):
        """Test getting a specific project."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )

        # Create active conversation for the project (required by get_project endpoint)
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=created_project.id,
            agent_role=AgentRoleType.PROJECT,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
            is_active=True,
        )
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        update_data = {"name": "Updated Project Name"}
        response = client.patch(f"/api/projects/{created_project.id}", json=update_data)
        assert response.status_code == 200

        updated_project = response.json()
        assert updated_project["name"] == "Updated Project Name"
        assert updated_project["description"] == test_project_data["description"]  # Unchanged

    def test_update_project_not_found(self, client):
        """Test updating a non-existent project."""
        update_data = {"name": "Updated Name"}
        response = client.patch("/api/projects/999", json=update_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

    def test_update_project_specification_content(self, client, db_session, test_project_data):
        """Test updating project specification content."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()
        db_session.refresh(created_project)

        # Update specification content
        new_specification = "This is the updated project specification with detailed requirements."
        update_data = {"specification": new_specification}
        response = client.patch(f"/api/projects/{created_project.id}", json=update_data)
        assert response.status_code == 200

        # Verify the specification content was updated
        updated_project = response.json()
        assert updated_project["specification"]["content"] == new_specification
        assert updated_project["name"] == test_project_data["name"]  # Other fields unchanged
        assert updated_project["description"] == test_project_data["description"]

    def test_delete_project_success(self, client, db_session, test_project_data):
        """Test deleting a project."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        response = client.get(f"/api/projects/{created_project.id}/resources")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_project_resources_with_data(self, client, db_session, test_project_data, test_resource_data):
        """Test listing project resources with existing data."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
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

    def test_create_project_resource(self, client, db_session, test_project_data, test_resource_data):
        """Test creating a new project resource."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        response = client.post(f"/api/projects/{created_project.id}/resources", json=test_resource_data)
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

    def test_delete_project_resource_success(self, client, db_session, test_project_data, test_resource_data):
        """Test deleting a project resource."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
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
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        response = client.get(f"/api/projects/{created_project.id}/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_project_tasks_with_data(self, client, db_session, test_project_data, test_task_data):
        """Test listing project tasks with existing data."""
        # Create test codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(
            name="Test Codebase",
            description="A test codebase",
            local_path="/tmp/test-codebase",
        )
        codebase = codebase_repo.create(codebase)
        db_session.commit()

        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        # Create test tasks
        task_repo = TaskRepository(db_session)
        task1_spec = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task1_plan = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        task1 = task_repo.create(
            project_id=created_project.id,
            title="Task 1",
            status=test_task_data["status"],
            specification=task1_spec,
            implementation_plan=task1_plan,
            base_branch="main",
            codebase_id=codebase.id,
        )
        task2_spec = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task2_plan = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        task2 = task_repo.create(
            project_id=created_project.id,
            title="Task 2",
            status=test_task_data["status"],
            specification=task2_spec,
            implementation_plan=task2_plan,
            base_branch="main",
            codebase_id=codebase.id,
        )

        # Create conversations for tasks
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task1.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task2.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
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

    def test_create_project_task(self, client, db_session, test_project_data, test_task_data):
        """Test creating a new task under a project."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        # Create task under project (no project_id or status in body - status always defaults to DEFINING)
        api_task_data = {
            "title": test_task_data["title"],
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == test_task_data["title"]
        assert task_data["status"] == "defining"  # Always DEFINING when created
        assert task_data["project_id"] == created_project.id
        assert "id" in task_data
        assert "conversation_id" in task_data
        assert isinstance(task_data["conversation_id"], int)

    def test_create_project_task_with_specification_content(self, client, db_session, test_project_data):
        """Test creating a task with initial specification content."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        # Create task with specification content (status not provided, defaults to DEFINING)
        api_task_data = {
            "title": "Task with Specification",
            "specification_content": "This is the initial task specification content.",
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == api_task_data["title"]
        assert task_data["status"] == "defining"  # Always DEFINING when created
        assert task_data["specification"]["content"] == api_task_data["specification_content"]
        assert task_data["implementation_plan"] is None  # Should be None initially

    def test_create_project_task_with_codebase(self, client, db_session, test_project_data):
        """Test creating a task with a codebase association."""

        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )

        # Create test codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(
            name="Test Codebase",
            description="A test codebase",
            local_path="/path/to/codebase",
        )
        codebase = codebase_repo.create(codebase)
        db_session.commit()

        # Create task with codebase (status not provided, defaults to DEFINING)
        api_task_data = {
            "title": "Task with Codebase",
            "codebase_id": codebase.id,
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == api_task_data["title"]
        assert task_data["status"] == "defining"  # Always DEFINING when created
        assert task_data["codebase_id"] == codebase.id

    def test_create_project_task_with_specification_and_codebase(self, client, db_session, test_project_data):
        """Test creating a task with both specification content and codebase."""

        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )

        # Create test codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(
            name="Test Codebase",
            description="A test codebase",
            local_path="/path/to/codebase",
        )
        codebase = codebase_repo.create(codebase)
        db_session.commit()

        # Create task with both (status not provided, defaults to DEFINING)
        api_task_data = {
            "title": "Task with Both",
            "specification_content": "Task specification for the codebase work.",
            "codebase_id": codebase.id,
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == api_task_data["title"]
        assert task_data["status"] == "defining"  # Always DEFINING when created
        assert task_data["specification"]["content"] == api_task_data["specification_content"]
        assert task_data["codebase_id"] == codebase.id

    def test_create_project_task_project_not_found(self, client, test_task_data):
        """Test creating a task for non-existent project."""
        api_task_data = {
            "title": test_task_data["title"],
        }
        response = client.post("/api/projects/999/tasks", json=api_task_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"
