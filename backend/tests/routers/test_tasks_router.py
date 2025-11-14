"""Tests for tasks router."""

import datetime
import json
from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.engines.internal import PydanticAIConversationService
from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.role_types import AgentRoleType
from devboard.agents.roles.task_planning import TaskPlanningRole
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


@pytest.fixture
def mock_task_service_for_workflow():
    """Mock TaskService for workflow action tests."""
    from unittest.mock import MagicMock

    from devboard.db.models.task import TaskStatus

    service = MagicMock()

    # Mock transition methods to just update status
    def mock_transition_to_planning(task):
        task.status = TaskStatus.PLANNING
        return task

    def mock_transition_to_implementing(task):
        task.status = TaskStatus.IMPLEMENTING
        return task

    service.transition_to_planning.side_effect = mock_transition_to_planning
    service.transition_to_implementing.side_effect = mock_transition_to_implementing

    return service


@pytest.fixture
def mock_agent_conversation_service_for_workflow(mock_agent, db_session, mock_agent_config_service, monkeypatch):
    """Create a conversation service with mocked agent for workflow tests."""

    def _create_service(conversation, task, document_repo):
        # Create role for the service
        role = TaskPlanningRole(
            task=task,
            document_repository=document_repo,
            agent_config_service=mock_agent_config_service,
        )

        service = PydanticAIConversationService(
            conversation=conversation,
            role=role,
            conversation_repository=ConversationRepository(db_session),
        )

        # Patch the _get_agent method to return our mock
        monkeypatch.setattr(service, "_get_agent", lambda conversation_history: mock_agent)

        return service

    return _create_service


@pytest.fixture
def client_with_mock_workflow_deps(
    client,
    mock_task_service_for_workflow,
) -> Iterator[TestClient]:
    """Client with mocked dependencies for workflow actions."""
    from devboard.api.dependencies.services import get_task_service
    from devboard.api.main import app

    app.dependency_overrides[get_task_service] = lambda: mock_task_service_for_workflow
    yield client
    if get_task_service in app.dependency_overrides:
        del app.dependency_overrides[get_task_service]


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


class TestWorkflowActions:
    """Test workflow action endpoints."""

    @pytest.fixture
    def test_task_for_workflow(self, db_session):
        """Create a test task with conversation for workflow tests."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project",
            description="A test project for development",
            specification=spec_doc,
        )

        # Create test task
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "Test task specification")
        task = task_repo.create(
            project_id=created_project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
        )

        # Create conversation for task
        conversation_repo = ConversationRepository(db_session)
        conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task.id,
            agent_role=AgentRoleType.TASK_PLANNING,
            engine=AgentEngine.INTERNAL,
            model_id="anthropic:claude-sonnet-4.5",
            is_active=True,
        )
        db_session.commit()

        return task

    def test_stream_workflow_action(
        self, client_with_mock_workflow_deps, test_task_for_workflow, mock_agent, monkeypatch
    ):
        """Test streaming a workflow action."""

        # Set up mock agent to return events
        async def mock_stream(prompt_or_approvals):
            yield TextMessage(
                role=MessageRole.AGENT,
                text_content="Creating implementation plan...",
                timestamp=datetime.datetime.now(datetime.UTC),
            )

        mock_agent.stream_events = mock_stream

        # Patch PydanticAIConversationService._get_agent to return our mock
        from devboard.agents.engines.internal.agent_conversation import PydanticAIConversationService

        monkeypatch.setattr(PydanticAIConversationService, "_get_agent", lambda self, conversation_history: mock_agent)

        prompt_action_request = {"action_key": "task.create_implementation_plan"}

        response = client_with_mock_workflow_deps.post(
            f"/api/tasks/{test_task_for_workflow.id}/workflow-action",
            json=prompt_action_request,
        )
        assert response.status_code == 200

        # Parse NDJSON response
        lines = response.text.strip().split("\n")
        events = [json.loads(line) for line in lines if line]

        # Should have SystemEvent for task update and agent message
        assert len(events) >= 1
        # Check that we got events back
        assert any(e["event_type"] in ["message", "system"] for e in events)

    def test_stream_workflow_action_not_found(self, client_with_mock_workflow_deps, test_task_for_workflow):
        """Test streaming a non-existent workflow action."""
        prompt_action_request = {"action_key": "nonexistent.action"}

        response = client_with_mock_workflow_deps.post(
            f"/api/tasks/{test_task_for_workflow.id}/workflow-action",
            json=prompt_action_request,
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_stream_workflow_action_archived_conversation(
        self, client_with_mock_workflow_deps, test_task_for_workflow, db_session
    ):
        """Test streaming workflow action on archived conversation."""
        # Archive the conversation
        conversation_repo = ConversationRepository(db_session)
        conversation = conversation_repo.get_active_conversation_for_entity(
            ParentEntityType.TASK, test_task_for_workflow.id
        )
        conversation.is_active = False
        db_session.commit()

        prompt_action_request = {"action_key": "task.create_implementation_plan"}

        response = client_with_mock_workflow_deps.post(
            f"/api/tasks/{test_task_for_workflow.id}/workflow-action",
            json=prompt_action_request,
        )
        assert response.status_code == 400
        assert "no active conversation" in response.json()["detail"].lower()
