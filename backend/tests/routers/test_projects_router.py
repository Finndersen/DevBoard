"""Tests for projects router."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

# from devboard.api.dependencies.agents import get_project_agent  # Removed in refactor
from devboard.agents.engines import AgentEngine
from devboard.agents.language_models import ModelType
from devboard.agents.roles import AgentRoleType
from devboard.agents.title_generator import TaskGenerationResult
from devboard.db.models import CustomFieldType, ParentEntityType
from devboard.db.models.codebase import Codebase
from devboard.db.models.document import DocumentType
from devboard.db.models.enums import EntityType
from devboard.db.repositories import (
    CodebaseRepository,
    ConversationRepository,
    CustomFieldRepository,
    DocumentRepository,
    LogEntryRepository,
    ProjectRepository,
    TaskRepository,
)


@pytest.fixture
def test_project_data():
    """Sample project data for testing."""
    return {"name": "Test Project", "description": "A test project for development"}


@pytest.fixture
def test_task_data():
    """Sample task data for testing (without project_id)."""
    return {
        "title": "Test Task",
        "description": "Test task description",
        "status": "planning",
    }


class TestProjectsRouter:
    """Test projects router endpoints."""

    @pytest.fixture(autouse=True)
    def mock_project_directory(self):
        with patch("devboard.services.project_service.ensure_project_directory"):
            yield

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

        # Verify the response contains document ID (content fetched separately)
        updated_project = response.json()
        assert updated_project["specification_document_id"] == spec_doc.id
        assert updated_project["name"] == test_project_data["name"]
        assert updated_project["description"] == test_project_data["description"]
        assert "specification_document_id" in updated_project

        # Verify the specification content was actually updated by fetching via API
        doc_response = client.get(f"/api/documents/{updated_project['specification_document_id']}")
        assert doc_response.status_code == 200
        assert doc_response.json()["content"] == new_specification

        # Verify the document content was actually updated by re-querying from DB
        updated_spec = document_repo.get_by_id(spec_doc.id)
        assert updated_spec.content == new_specification

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


class TestProjectCustomFieldsRouter:
    """Test project custom fields endpoints."""

    @pytest.fixture(autouse=True)
    def mock_project_directory(self):
        with patch("devboard.services.project_service.ensure_project_directory"):
            yield

    def test_create_project_with_custom_fields(self, client, db_session):
        """Test creating a project with custom field values persists them."""
        project_data = {
            "name": "CF Test Project",
            "description": "A project with custom fields",
            "custom_fields": {"priority": "high", "reviewed": True},
        }
        response = client.post("/api/projects/", json=project_data)
        assert response.status_code == 200

        project = response.json()
        assert project["custom_fields"] == {"priority": "high", "reviewed": True}

    def test_create_project_no_custom_fields(self, client):
        """Test creating a project without custom fields returns null custom_fields."""
        project_data = {"name": "No CF Project", "description": "No custom fields"}
        response = client.post("/api/projects/", json=project_data)
        assert response.status_code == 200
        assert response.json()["custom_fields"] is None

    def test_create_project_missing_mandatory_field_returns_400(self, client, db_session):
        """Test creating a project when mandatory custom fields are missing returns 400."""
        custom_field_repo = CustomFieldRepository(db_session)
        custom_field_repo.create(
            name="team",
            field_type=CustomFieldType.TEXT,
            entity_type=EntityType.PROJECT,
            mandatory=True,
        )
        db_session.commit()

        response = client.post("/api/projects/", json={"name": "Missing CF Project", "description": "desc"})
        assert response.status_code == 400
        assert "team" in response.json()["detail"]

    def test_create_project_with_mandatory_field_filled(self, client, db_session):
        """Test creating a project with all mandatory custom fields filled succeeds."""
        custom_field_repo = CustomFieldRepository(db_session)
        custom_field_repo.create(
            name="owner",
            field_type=CustomFieldType.TEXT,
            entity_type=EntityType.PROJECT,
            mandatory=True,
        )
        db_session.commit()

        project_data = {
            "name": "With Mandatory CF",
            "description": "desc",
            "custom_fields": {"owner": "alice"},
        }
        response = client.post("/api/projects/", json=project_data)
        assert response.status_code == 200
        assert response.json()["custom_fields"] == {"owner": "alice"}

    def test_get_project_returns_custom_fields(self, client, db_session):
        """Test that get_project endpoint includes custom_fields in response."""
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        conversation_repo = ConversationRepository(db_session)

        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="CF Get Project",
            description="desc",
            specification=spec_doc,
            custom_fields={"status": "active"},
        )
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
        assert response.json()["custom_fields"] == {"status": "active"}

    def test_update_project_custom_fields_merges_values(self, client, db_session):
        """Test updating custom fields merges provided values with existing ones."""
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)

        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Merge CF Project",
            description="desc",
            specification=spec_doc,
            custom_fields={"existing": "value", "other": "kept"},
        )
        db_session.commit()

        response = client.patch(
            f"/api/projects/{created_project.id}", json={"custom_fields": {"existing": "updated", "new": "added"}}
        )
        assert response.status_code == 200

        project = response.json()
        assert project["custom_fields"] == {"existing": "updated", "other": "kept", "new": "added"}

    def test_update_project_custom_fields_removes_none_values(self, client, db_session):
        """Test updating custom fields with None values removes those keys."""
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)

        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Remove CF Project",
            description="desc",
            specification=spec_doc,
            custom_fields={"keep": "value", "remove": "this"},
        )
        db_session.commit()

        response = client.patch(f"/api/projects/{created_project.id}", json={"custom_fields": {"remove": None}})
        assert response.status_code == 200

        project = response.json()
        assert project["custom_fields"] == {"keep": "value"}

    def test_update_project_without_custom_fields_leaves_them_unchanged(self, client, db_session):
        """Test that updates not including custom_fields leave them unchanged."""
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)

        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Unchanged CF Project",
            description="desc",
            specification=spec_doc,
            custom_fields={"preserved": "value"},
        )
        db_session.commit()

        response = client.patch(f"/api/projects/{created_project.id}", json={"name": "Updated Name"})
        assert response.status_code == 200

        project = response.json()
        assert project["name"] == "Updated Name"
        assert project["custom_fields"] == {"preserved": "value"}


class TestProjectTasksRouter:
    """Test project tasks router endpoints."""

    @pytest.fixture(autouse=True)
    def mock_git(self):
        from devboard.integrations.base import IntegrationConnectionResult

        with patch("devboard.services.task_git.service.GitRepoIntegration") as mock_cls:
            mock_instance = mock_cls.return_value
            mock_instance.validate = AsyncMock(return_value=IntegrationConnectionResult(success=True, message="ok"))
            mock_instance.branch_exists = AsyncMock(return_value=True)
            yield mock_cls

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
            branch_name="feature/test-task",
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
            branch_name="feature/test-task",
        )

        # Create conversations for tasks
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task1.id,
            agent_role=AgentRoleType.TASK_PLANNING,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task2.id,
            agent_role=AgentRoleType.TASK_PLANNING,
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

    def test_create_project_task(self, client, db_session, test_project_data, test_task_data, test_codebase):
        """Test creating a new task under a project."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        # Create task under project (no project_id or status in body - status always defaults to PLANNING)
        api_task_data = {
            "title": test_task_data["title"],
            "codebase_id": test_codebase.id,
            "base_branch": "main",
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == test_task_data["title"]
        assert task_data["status"] == "planning"  # Always PLANNING when created
        assert task_data["project_id"] == created_project.id
        assert "id" in task_data
        assert "conversation_id" in task_data
        assert isinstance(task_data["conversation_id"], int)

    def test_create_project_task_with_specification_content(self, client, db_session, test_project_data, test_codebase):
        """Test creating a task with initial specification content."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        # Create task with specification content (status not provided, defaults to PLANNING)
        api_task_data = {
            "title": "Task with Specification",
            "specification_content": "This is the initial task specification content.",
            "codebase_id": test_codebase.id,
            "base_branch": "main",
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == api_task_data["title"]
        assert task_data["status"] == "planning"  # Always PLANNING when created
        assert task_data["specification_document_id"] is not None
        assert task_data["implementation_plan_document_id"] is None  # Should be None initially

        # Verify the specification content was created correctly via API
        doc_response = client.get(f"/api/documents/{task_data['specification_document_id']}")
        assert doc_response.status_code == 200
        assert doc_response.json()["content"] == api_task_data["specification_content"]

    def test_create_project_task_with_codebase(self, client, db_session, test_project_data, test_codebase):
        """Test creating a task with a codebase association."""

        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        # Create task with codebase (status not provided, defaults to PLANNING)
        api_task_data = {
            "title": "Task with Codebase",
            "codebase_id": test_codebase.id,
            "base_branch": "main",
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == api_task_data["title"]
        assert task_data["status"] == "planning"  # Always PLANNING when created
        assert task_data["codebase_id"] == test_codebase.id

    def test_create_project_task_with_specification_and_codebase(
        self, client, db_session, test_project_data, test_codebase
    ):
        """Test creating a task with both specification content and codebase."""

        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        # Create task with both (status not provided, defaults to PLANNING)
        api_task_data = {
            "title": "Task with Both",
            "specification_content": "Task specification for the codebase work.",
            "codebase_id": test_codebase.id,
            "base_branch": "main",
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == api_task_data["title"]
        assert task_data["status"] == "planning"  # Always PLANNING when created
        assert task_data["specification_document_id"] is not None
        assert task_data["codebase_id"] == test_codebase.id

        # Verify the specification content was set correctly
        task_spec = document_repo.get_by_id(task_data["specification_document_id"])
        assert task_spec.content == api_task_data["specification_content"]

    def test_create_project_task_project_not_found(self, client, test_task_data, test_codebase):
        """Test creating a task for non-existent project."""
        api_task_data = {
            "title": test_task_data["title"],
            "codebase_id": test_codebase.id,
            "base_branch": "main",
        }
        response = client.post("/api/projects/999/tasks", json=api_task_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

    def test_create_project_task_with_title_only(self, client, db_session, test_project_data, test_codebase):
        """Test creating a task with title only (existing behavior)."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        api_task_data = {
            "title": "Task created with title only",
            "codebase_id": test_codebase.id,
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == "Task created with title only"
        assert task_data["status"] == "planning"

    @patch("devboard.api.routers.projects.generate_task_title_and_branch")
    @patch("devboard.api.routers.projects.get_execution_manager")
    def test_create_project_task_with_initial_message_only(
        self, mock_get_execution_manager, mock_generate_title, client, db_session, test_project_data, test_codebase
    ):
        """Test creating a task with initial_message only (generates title, starts agent)."""
        # Mock title generation
        mock_generate_title.return_value = TaskGenerationResult(
            title="Generated Task Title", branch_name="generated-task-title", model_type=ModelType.STANDARD
        )

        # Mock execution manager
        mock_manager = Mock()
        mock_get_execution_manager.return_value = mock_manager

        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        api_task_data = {
            "codebase_id": test_codebase.id,
            "initial_message": "Please help me implement user authentication",
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == "Generated Task Title"
        assert task_data["status"] == "planning"

        # Verify title generation was called with initial message
        mock_generate_title.assert_called_once_with("Please help me implement user authentication")

        # Verify agent execution was started
        mock_manager.start_agent_execution.assert_called_once()
        # Get the call arguments
        call_args = mock_manager.start_agent_execution.call_args
        assert call_args[0][1] == "Please help me implement user authentication"  # Second arg is the message

    @patch("devboard.api.routers.projects.generate_task_title_and_branch")
    @patch("devboard.api.routers.projects.get_execution_manager")
    def test_create_project_task_with_title_and_initial_message(
        self, mock_get_execution_manager, mock_generate_title, client, db_session, test_project_data, test_codebase
    ):
        """Test creating a task with both title and initial_message provided."""
        # Mock execution manager
        mock_manager = Mock()
        mock_get_execution_manager.return_value = mock_manager

        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        api_task_data = {
            "title": "Custom Task Title",
            "codebase_id": test_codebase.id,
            "initial_message": "Please help me implement user authentication",
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        assert task_data["title"] == "Custom Task Title"  # Uses provided title, not generated
        assert task_data["status"] == "planning"

        # Verify title generation was NOT called (since title was provided)
        mock_generate_title.assert_not_called()

        # Verify agent execution was still started
        mock_manager.start_agent_execution.assert_called_once()

    def test_create_project_task_with_neither_title_nor_initial_message(
        self, client, db_session, test_project_data, test_codebase
    ):
        """Test creating a task with neither title nor initial_message (validation error)."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        api_task_data = {
            "codebase_id": test_codebase.id,
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 422  # Validation error
        assert "Either title or initial_message must be provided" in str(response.json())

    @patch("devboard.api.routers.projects.generate_task_title_and_branch")
    def test_create_project_task_title_generation_fallback(
        self, mock_generate_title, client, db_session, test_project_data, test_codebase
    ):
        """Test that task creation handles title generation failures gracefully."""
        # Mock title generation failure by returning a fallback result
        mock_generate_title.return_value = TaskGenerationResult(
            title="task-1642501234", branch_name="task-1642501234", model_type=ModelType.STANDARD
        )

        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"], specification=spec_doc
        )
        db_session.commit()

        api_task_data = {
            "codebase_id": test_codebase.id,
            "initial_message": "A very long message " * 10,  # Long message to test fallback handling
        }

        response = client.post(f"/api/projects/{created_project.id}/tasks", json=api_task_data)
        assert response.status_code == 200

        task_data = response.json()
        # Should use fallback title from mock
        assert task_data["title"] == "task-1642501234"


class TestCreateProjectTaskModelType:
    """Tests for model_type parameter in create_project_task endpoint."""

    @pytest.fixture(autouse=True)
    def mock_git(self):
        from devboard.integrations.base import IntegrationConnectionResult

        with patch("devboard.services.task_git.service.GitRepoIntegration") as mock_cls:
            mock_instance = mock_cls.return_value
            mock_instance.validate = AsyncMock(return_value=IntegrationConnectionResult(success=True, message="ok"))
            mock_instance.branch_exists = AsyncMock(return_value=True)
            yield mock_cls

    def _create_project(self, db_session, test_project_data):
        """Helper to create a project directly in the DB."""
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(
            name=test_project_data["name"],
            description=test_project_data["description"],
            specification=spec_doc,
        )
        db_session.commit()
        return project

    def _make_mock_agent_config_service(self, engine=AgentEngine.INTERNAL, resolved_model_id="anthropic:claude-opus-4"):
        """Build a mock AgentConfigService that returns a proper config with a given resolved model_id."""
        from devboard.agents.config_types import AgentEngineModelConfig

        mock_service = Mock()
        # Return a real AgentEngineModelConfig so conversation service can call .model safely
        effective_config = AgentEngineModelConfig(engine=engine, model_db=None)
        mock_service.get_effective_config.return_value = effective_config
        mock_service.get_model_id_for_type.return_value = resolved_model_id
        return mock_service

    @patch("devboard.api.routers.projects.generate_task_title_and_branch")
    @patch("devboard.api.routers.projects.get_execution_manager")
    def test_explicit_model_type_resolves_to_model_id(
        self, mock_get_execution_manager, mock_generate_title, client, db_session, test_project_data, test_codebase
    ):
        """Explicit model_type resolves via AgentConfigService and is passed to task creation."""
        from devboard.api.dependencies.services import get_agent_config_service
        from devboard.api.main import app

        mock_generate_title.return_value = TaskGenerationResult(
            title="Generated Title", branch_name="generated-title", model_type=ModelType.STANDARD
        )
        mock_get_execution_manager.return_value = Mock()
        mock_agent_config_service = self._make_mock_agent_config_service(resolved_model_id="anthropic:claude-haiku-4-5")

        project = self._create_project(db_session, test_project_data)

        app.dependency_overrides[get_agent_config_service] = lambda: mock_agent_config_service
        try:
            response = client.post(
                f"/api/projects/{project.id}/tasks",
                json={"codebase_id": test_codebase.id, "initial_message": "Fix the bug", "model_type": "fast"},
            )
        finally:
            del app.dependency_overrides[get_agent_config_service]

        assert response.status_code == 200
        # get_effective_config called at least once for model_type resolution (also called by conversation service)
        mock_agent_config_service.get_effective_config.assert_called_with(AgentRoleType.TASK_PLANNING)
        mock_agent_config_service.get_model_id_for_type.assert_called_once_with(
            ModelType.FAST, mock_agent_config_service.get_effective_config.return_value.engine
        )

    @patch("devboard.api.routers.projects.generate_task_title_and_branch")
    @patch("devboard.api.routers.projects.get_execution_manager")
    def test_auto_model_type_reuses_title_result(
        self, mock_get_execution_manager, mock_generate_title, client, db_session, test_project_data, test_codebase
    ):
        """model_type='auto' with no title uses model_type from title generation result."""
        from devboard.api.dependencies.services import get_agent_config_service
        from devboard.api.main import app

        mock_generate_title.return_value = TaskGenerationResult(
            title="Generated Title", branch_name="generated-title", model_type=ModelType.ADVANCED
        )
        mock_get_execution_manager.return_value = Mock()
        mock_agent_config_service = self._make_mock_agent_config_service(resolved_model_id="anthropic:claude-opus-4")

        project = self._create_project(db_session, test_project_data)

        app.dependency_overrides[get_agent_config_service] = lambda: mock_agent_config_service
        try:
            response = client.post(
                f"/api/projects/{project.id}/tasks",
                json={"codebase_id": test_codebase.id, "initial_message": "Big refactor", "model_type": "auto"},
            )
        finally:
            del app.dependency_overrides[get_agent_config_service]

        assert response.status_code == 200
        # generate_task_title_and_branch should be called exactly once (not twice)
        mock_generate_title.assert_called_once()
        mock_agent_config_service.get_model_id_for_type.assert_called_once_with(
            ModelType.ADVANCED, mock_agent_config_service.get_effective_config.return_value.engine
        )

    @patch("devboard.api.routers.projects.generate_task_title_and_branch")
    @patch("devboard.api.routers.projects.get_execution_manager")
    def test_auto_model_type_with_title_calls_generator_separately(
        self, mock_get_execution_manager, mock_generate_title, client, db_session, test_project_data, test_codebase
    ):
        """model_type='auto' with explicit title calls generator separately to get model_type."""
        from devboard.api.dependencies.services import get_agent_config_service
        from devboard.api.main import app

        mock_generate_title.return_value = TaskGenerationResult(
            title="Ignored Title", branch_name="ignored-title", model_type=ModelType.STANDARD
        )
        mock_get_execution_manager.return_value = Mock()
        mock_agent_config_service = self._make_mock_agent_config_service(resolved_model_id="anthropic:claude-sonnet-4")

        project = self._create_project(db_session, test_project_data)

        app.dependency_overrides[get_agent_config_service] = lambda: mock_agent_config_service
        try:
            response = client.post(
                f"/api/projects/{project.id}/tasks",
                json={
                    "title": "Explicit Title",
                    "codebase_id": test_codebase.id,
                    "initial_message": "Moderate change",
                    "model_type": "auto",
                },
            )
        finally:
            del app.dependency_overrides[get_agent_config_service]

        assert response.status_code == 200
        # generator called separately (title was provided so first call didn't happen)
        mock_generate_title.assert_called_once_with("Moderate change")
        mock_agent_config_service.get_model_id_for_type.assert_called_once_with(
            ModelType.STANDARD, mock_agent_config_service.get_effective_config.return_value.engine
        )

    def test_no_model_type_skips_resolution(self, client, db_session, test_project_data, test_codebase):
        """Omitting model_type does not call get_model_id_for_type."""
        from devboard.api.dependencies.services import get_agent_config_service
        from devboard.api.main import app

        mock_agent_config_service = self._make_mock_agent_config_service()

        project = self._create_project(db_session, test_project_data)

        app.dependency_overrides[get_agent_config_service] = lambda: mock_agent_config_service
        try:
            response = client.post(
                f"/api/projects/{project.id}/tasks",
                json={"title": "Simple Task", "codebase_id": test_codebase.id},
            )
        finally:
            del app.dependency_overrides[get_agent_config_service]

        assert response.status_code == 200
        mock_agent_config_service.get_model_id_for_type.assert_not_called()


class TestProjectEventEmission:
    """Test that project lifecycle events are emitted as log entries."""

    def _create_project(self, db_session):
        """Helper to create a project directly in the DB."""
        document_repo = DocumentRepository(db_session)
        project_repo = ProjectRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(
            name="Event Test Project",
            description="A project for event testing",
            specification=spec_doc,
        )
        db_session.commit()
        return project

    def test_patch_emits_project_updated_event(self, client, db_session):
        """PATCH /projects/{id} emits a project.updated log entry."""
        project = self._create_project(db_session)
        log_entry_repo = LogEntryRepository(db_session)

        response = client.patch(f"/api/projects/{project.id}", json={"name": "New Name"})
        assert response.status_code == 200

        entries = log_entry_repo.query(type_pattern="project.updated")
        assert len(entries) >= 1
        entry = next(e for e in entries if e.project_id == project.id)
        assert entry.type == "project.updated"
        assert entry.entry_metadata is not None
        assert entry.entry_metadata["changed_fields"] == ["name"]

    def test_patch_changed_fields_includes_specification(self, client, db_session):
        """PATCH with specification update lists 'specification' in changed_fields."""
        project = self._create_project(db_session)
        log_entry_repo = LogEntryRepository(db_session)

        response = client.patch(f"/api/projects/{project.id}", json={"specification": "New spec content"})
        assert response.status_code == 200

        entries = log_entry_repo.query(type_pattern="project.updated")
        entry = next(e for e in entries if e.project_id == project.id)
        assert entry.entry_metadata is not None
        assert "specification" in entry.entry_metadata["changed_fields"]

    def test_delete_emits_project_deleted_event(self, client, db_session):
        """DELETE /projects/{id} emits a project.deleted log entry before deletion."""
        project = self._create_project(db_session)
        project_id = project.id
        project_name = project.name
        log_entry_repo = LogEntryRepository(db_session)

        response = client.delete(f"/api/projects/{project_id}")
        assert response.status_code == 200

        entries = log_entry_repo.query(type_pattern="project.deleted")
        assert len(entries) >= 1
        entry = next(
            e for e in entries if e.entry_metadata is not None and e.entry_metadata.get("project_name") == project_name
        )
        assert entry.type == "project.deleted"
        assert entry.entry_metadata == {"project_name": project_name}

    def test_delete_not_found_does_not_emit_event(self, client, db_session):
        """DELETE /projects/{id} for nonexistent project returns 404 without emitting."""
        log_entry_repo = LogEntryRepository(db_session)
        entries_before = log_entry_repo.query(type_pattern="project.deleted")

        response = client.delete("/api/projects/99999")
        assert response.status_code == 404

        entries_after = log_entry_repo.query(type_pattern="project.deleted")
        assert len(entries_after) == len(entries_before)
