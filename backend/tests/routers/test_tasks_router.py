"""Tests for tasks router."""

import datetime
import json
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from devboard.agents.engines import AgentEngine
from devboard.agents.engines.internal import PydanticAIConversationService
from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.roles import AgentRoleType
from devboard.agents.roles.task_planning import TaskPlanningRole
from devboard.db.models import ParentEntityType
from devboard.db.models.codebase import Codebase
from devboard.db.models.document import DocumentType
from devboard.db.models.task import Task, TaskStatus
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
    from unittest.mock import Mock

    from devboard.api.dependencies.services import get_task_service, get_workspace_allocation_service
    from devboard.api.main import app

    # Mock workspace allocation service to avoid git worktree operations
    mock_workspace_service = Mock()

    # Make run_task_agent_in_workspace pass through the agent stream unchanged
    async def passthrough_stream(task, agent_stream):
        async for event in agent_stream:
            yield event

    mock_workspace_service.run_task_agent_in_workspace = passthrough_stream

    app.dependency_overrides[get_task_service] = lambda: mock_task_service_for_workflow
    app.dependency_overrides[get_workspace_allocation_service] = lambda: mock_workspace_service
    yield client
    if get_task_service in app.dependency_overrides:
        del app.dependency_overrides[get_task_service]
    if get_workspace_allocation_service in app.dependency_overrides:
        del app.dependency_overrides[get_workspace_allocation_service]


class TestTasksRouter:
    """Test tasks router endpoints."""

    def test_get_task_success(self, client, db_session, test_codebase, test_task_data):
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
            base_branch="main",
            codebase_id=test_codebase.id,
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

    def test_get_task_not_found(self, client, test_codebase):
        """Test getting a non-existent task."""

        response = client.get("/api/tasks/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_update_task_success(self, client, db_session, test_codebase, test_task_data):
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
            base_branch="main",
            codebase_id=test_codebase.id,
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

    def test_update_task_not_found(self, client, test_codebase):
        """Test updating a non-existent task."""

        update_data = {"title": "Updated Title"}
        response = client.patch("/api/tasks/999", json=update_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_delete_task_success(self, client, db_session, test_codebase, test_task_data, test_resource_data):
        """Test deleting a task with comprehensive cleanup."""
        from sqlalchemy import select

        from devboard.db.models import ConversationMessage
        from devboard.db.models.base import task_context_resource_association

        # Create test project using repository
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        created_project = project_repo.create(
            name="Test Project", description="A test project for development", specification=spec_doc
        )

        # Create test task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "Test spec content")
        task_plan_doc = document_repo.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "Test plan content")
        created_task = task_repo.create(
            project_id=created_project.id,
            title=test_task_data["title"],
            status=test_task_data["status"],
            specification=task_spec_doc,
            implementation_plan=task_plan_doc,
            base_branch="main",
            codebase_id=test_codebase.id,
        )

        # Create conversation and messages for the task
        conversation_repo = ConversationRepository(db_session)
        conversation = conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=created_task.id,
            agent_role=AgentRoleType.TASK_SPECIFICATION,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
        )

        # Add some messages to the conversation
        from devboard.db.models import MessageType

        message1 = ConversationMessage(
            conversation_id=conversation.id,
            message_type=MessageType.USER_PROMPT,
            pydantic_content={"parts": [{"content": "Test message 1"}]},
            text_content="Test message 1",
        )
        message2 = ConversationMessage(
            conversation_id=conversation.id,
            message_type=MessageType.TEXT_RESPONSE,
            pydantic_content={"parts": [{"content": "Test response 1"}]},
            text_content="Test response 1",
        )
        db_session.add(message1)
        db_session.add(message2)

        # Create a context resource and associate it with the task
        resource_repo = ContextProviderResourceRepository(db_session)
        resource = resource_repo.create_task_resource(
            task_id=created_task.id,
            resource_uri=test_resource_data["resource_uri"],
            provider_name="github",
            description=test_resource_data["description"],
        )

        db_session.commit()

        # Store IDs for verification after deletion
        task_id = created_task.id
        conversation_id = conversation.id
        spec_doc_id = task_spec_doc.id
        plan_doc_id = task_plan_doc.id
        resource_id = resource.id

        # Verify setup: task-context association exists
        assoc_stmt = select(task_context_resource_association).where(
            task_context_resource_association.c.task_id == task_id
        )
        assoc_before = db_session.execute(assoc_stmt).first()
        assert assoc_before is not None, "Task-context association should exist before deletion"

        # Delete the task
        response = client.delete(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Task deleted successfully"

        # Verify task is deleted
        get_response = client.get(f"/api/tasks/{task_id}")
        assert get_response.status_code == 404

        # Verify conversations are deleted
        deleted_conversation = conversation_repo.get_by_id(conversation_id)
        assert deleted_conversation is None, "Conversation should be deleted"

        # Verify messages are deleted
        messages_stmt = select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
        remaining_messages = db_session.execute(messages_stmt).scalars().all()
        assert len(remaining_messages) == 0, "All conversation messages should be deleted"

        # Verify task-context resource associations are deleted
        assoc_after = db_session.execute(assoc_stmt).first()
        assert assoc_after is None, "Task-context association should be deleted"

        # Verify resource itself still exists (it's M2M, resource should not be deleted)
        resource_after = resource_repo.get_by_id(resource_id)
        assert resource_after is not None, "Resource should still exist (not exclusive to task)"

        # Verify documents are deleted
        spec_doc_after = document_repo.get_by_id(spec_doc_id)
        plan_doc_after = document_repo.get_by_id(plan_doc_id)
        assert spec_doc_after is None, "Specification document should be deleted"
        assert plan_doc_after is None, "Implementation plan document should be deleted"

    def test_delete_task_with_branch_deletion(self, client, db_session):
        """Test deleting a task and its git branch."""
        # Create project using repository
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(
            name="Test Project", description="Test project description", specification=spec_doc
        )

        # Create codebase using repository
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(name="Test Codebase", description="Test codebase description", local_path="/test/path")
        codebase = codebase_repo.create(codebase)

        # Create task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task = task_repo.create(
            project_id=project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
            base_branch="main",
            codebase_id=codebase.id,
            branch_name="feature/test-branch",
        )
        db_session.commit()
        task_id = task.id

        # Mock GitRepoIntegration at the integration layer
        mock_git = MagicMock()
        mock_git.delete_branch = AsyncMock()

        # Patch GitRepoIntegration to return our mock
        with patch("devboard.services.task_git_service.GitRepoIntegration", return_value=mock_git):
            # Delete the task with delete_branch=true
            response = client.delete(f"/api/tasks/{task_id}?delete_branch=true")

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["message"] == "Task deleted successfully"

        # Verify task is deleted from database
        deleted_task = db_session.get(Task, task_id)
        assert deleted_task is None

        # Verify delete_branch was called with force=True
        mock_git.delete_branch.assert_called_once()
        call_args = mock_git.delete_branch.call_args
        assert call_args[0][0] == "feature/test-branch"  # Branch name
        assert call_args[1]["force"] is True  # force=True keyword arg

    def test_delete_task_without_branch_deletion(self, client, db_session):
        """Test deleting a task without deleting its git branch (default behavior)."""
        # Create project using repository
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(
            name="Test Project", description="Test project description", specification=spec_doc
        )

        # Create codebase using repository
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(name="Test Codebase", description="Test codebase description", local_path="/test/path")
        codebase = codebase_repo.create(codebase)

        # Create task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task = task_repo.create(
            project_id=project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
            base_branch="main",
            codebase_id=codebase.id,
            branch_name="feature/test-branch",
        )
        db_session.commit()
        task_id = task.id

        # Mock GitRepoIntegration at the integration layer
        mock_git = MagicMock()
        mock_git.delete_branch = AsyncMock()

        # Patch GitRepoIntegration to return our mock
        with patch("devboard.services.task_git_service.GitRepoIntegration", return_value=mock_git):
            # Delete the task without specifying delete_branch (defaults to False)
            response = client.delete(f"/api/tasks/{task_id}")

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify task is deleted from database
        deleted_task = db_session.get(Task, task_id)
        assert deleted_task is None

        # Verify delete_branch was NOT called (since delete_branch=False)
        mock_git.delete_branch.assert_not_called()

    def test_delete_task_with_branch_deletion_error_handling(self, client, db_session):
        """Test that task deletion succeeds even if branch deletion fails."""
        # Create project using repository
        project_repo = ProjectRepository(db_session)
        document_repo = DocumentRepository(db_session)
        spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(
            name="Test Project", description="Test project description", specification=spec_doc
        )

        # Create codebase using repository
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(name="Test Codebase", description="Test codebase description", local_path="/test/path")
        codebase = codebase_repo.create(codebase)

        # Create task using repository
        task_repo = TaskRepository(db_session)
        task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "")
        task = task_repo.create(
            project_id=project.id,
            title="Test Task",
            status=TaskStatus.DEFINING,
            specification=task_spec_doc,
            base_branch="main",
            codebase_id=codebase.id,
            branch_name="feature/test-branch",
        )
        db_session.commit()
        task_id = task.id

        # Mock GitRepoIntegration to raise an error
        mock_git = MagicMock()
        mock_git.delete_branch = AsyncMock(side_effect=Exception("Git error"))

        # Patch GitRepoIntegration to return our mock
        with patch("devboard.services.task_git_service.GitRepoIntegration", return_value=mock_git):
            # Delete the task with delete_branch=true
            response = client.delete(f"/api/tasks/{task_id}?delete_branch=true")

        # Task deletion should still succeed despite branch deletion error
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify task is deleted from database
        deleted_task = db_session.get(Task, task_id)
        assert deleted_task is None

    def test_delete_task_not_found(self, client, test_codebase):
        """Test deleting a non-existent task."""

        response = client.delete("/api/tasks/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_update_task_codebase_assignment(self, client, db_session, test_task):
        """Test updating task codebase assignment."""
        # Create a second test codebase for reassignment
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(
            name="Test Codebase 2",
            description="A second test codebase",
            local_path="/path/to/test/codebase2",
            repository_url="https://github.com/test/repo2",
        )
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        # Update task to assign second codebase
        update_data = {"codebase_id": created_codebase.id}
        response = client.patch(f"/api/tasks/{test_task.id}", json=update_data)
        assert response.status_code == 200

        updated_task = response.json()
        assert updated_task["codebase_id"] == created_codebase.id

        # Verify the update persisted
        get_response = client.get(f"/api/tasks/{test_task.id}")
        assert get_response.status_code == 200
        assert get_response.json()["codebase_id"] == created_codebase.id


class TestTaskResourcesRouter:
    """Test task resource endpoints."""

    def test_list_task_resources_empty(self, client, db_session, test_codebase, test_task_data):
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
            base_branch="main",
            codebase_id=test_codebase.id,
        )
        db_session.commit()

        response = client.get(f"/api/tasks/{created_task.id}/resources")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_task_resources_with_data(self, client, db_session, test_codebase, test_task_data, test_resource_data):
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
            base_branch="main",
            codebase_id=test_codebase.id,
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

    def test_list_task_resources_task_not_found(self, client, test_codebase):
        """Test listing resources for non-existent task."""
        response = client.get("/api/tasks/999/resources")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_create_task_resource(self, client, db_session, test_codebase, test_task_data, test_resource_data):
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
            base_branch="main",
            codebase_id=test_codebase.id,
        )
        db_session.commit()

        response = client.post(f"/api/tasks/{created_task.id}/resources", json=test_resource_data)
        assert response.status_code == 200

        resource_data = response.json()
        assert resource_data["resource_uri"] == test_resource_data["resource_uri"]
        assert resource_data["description"] == test_resource_data["description"]
        assert "id" in resource_data

    def test_create_task_resource_task_not_found(self, client, test_resource_data, test_codebase):
        """Test creating a resource for non-existent task."""
        response = client.post("/api/tasks/999/resources", json=test_resource_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_delete_task_resource_success(self, client, db_session, test_codebase, test_task_data, test_resource_data):
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
            base_branch="main",
            codebase_id=test_codebase.id,
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

    def test_delete_task_resource_task_not_found(self, client, test_codebase):
        """Test deleting a resource for non-existent task."""
        response = client.delete("/api/tasks/999/resources/1")
        assert response.status_code == 404
        assert response.json()["detail"] == "Task not found"

    def test_delete_task_resource_not_found(self, client, db_session, test_codebase, test_task_data):
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
            base_branch="main",
            codebase_id=test_codebase.id,
        )
        db_session.commit()

        response = client.delete(f"/api/tasks/{created_task.id}/resources/999")
        assert response.status_code == 404
        assert "Resource not found or does not belong to this task" in response.json()["detail"]


class TestTaskStateTransition:
    """Test task state transition API endpoints."""

    @pytest.fixture
    def test_task_with_project(self, db_session, test_codebase):
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
            base_branch="main",
            codebase_id=test_codebase.id,
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
    def test_task_for_workflow(self, db_session, test_codebase):
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
            base_branch="main",
            codebase_id=test_codebase.id,
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


@pytest.mark.asyncio
async def test_get_task_diff(client, db_session):
    """Test getting diff for a task with view parameter (new API)."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from devboard.db.models.document import DocumentType
    from devboard.db.repositories import CodebaseRepository, DocumentRepository, ProjectRepository, TaskRepository
    from devboard.integrations.types import FileDiff, StructuredDiff

    # Create specification document for project
    doc_repo = DocumentRepository(db_session)
    spec_doc = doc_repo.create(DocumentType.PROJECT_SPECIFICATION, "Test project specification")
    db_session.commit()

    # Create project with specification
    project_repo = ProjectRepository(db_session)
    project = project_repo.create(
        name="Test Project",
        description="Test description",
        specification=spec_doc,
    )
    db_session.commit()

    codebase_repo = CodebaseRepository(db_session)
    codebase = Codebase(
        name="Test Codebase",
        local_path="/tmp/test",
        description="Test codebase",
    )
    codebase = codebase_repo.create(codebase)
    db_session.commit()

    # Create task with specification
    task_spec_doc = doc_repo.create(DocumentType.TASK_SPECIFICATION, "Test task specification")
    db_session.commit()

    task_repo = TaskRepository(db_session)
    task = task_repo.create(
        title="Test Task",
        project_id=project.id,
        codebase_id=codebase.id,
        base_branch="main",
        specification=task_spec_doc,
        branch_name="feature/test-123",
    )
    db_session.commit()

    # Mock all changes diff (combines all commits + uncommitted)
    all_changes_diff = """diff --git a/file1.py b/file1.py
--- a/file1.py
+++ b/file1.py
@@ -1,3 +1,5 @@
+new line 1
+new line 2
 existing line
"""

    # Create mock structured diff to return
    mock_structured_diff = StructuredDiff(
        files=[
            FileDiff(
                file_path="file1.py",
                diff_content=all_changes_diff,
                additions=2,
                deletions=0,
            )
        ],
        additions=2,
        deletions=0,
    )

    # Mock GitRepoIntegration at the integration layer
    mock_git = MagicMock()
    mock_git.get_merge_base = AsyncMock(return_value="abc123")
    mock_git.get_structured_diff = AsyncMock(return_value=mock_structured_diff)

    # Patch GitRepoIntegration - this will affect code running during the request
    with patch("devboard.services.task_git_service.GitRepoIntegration", return_value=mock_git):
        # Test with view='all' parameter (required)
        response = client.get(f"/api/tasks/{task.id}/diff?view=all")

        assert response.status_code == 200
        data = response.json()

        # Check new simplified structure
        assert "files" in data
        assert "additions" in data
        assert "deletions" in data
        assert "generated_at" in data

        # Check files
        assert len(data["files"]) == 1
        assert data["files"][0]["file_path"] == "file1.py"
        assert data["files"][0]["additions"] == 2
        assert data["files"][0]["deletions"] == 0

        # Check totals
        assert data["additions"] == 2
        assert data["deletions"] == 0
