"""Tests for projects router."""

from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.run import AgentRunResult

from devboard.api.dependencies.agents import get_project_agent
from devboard.api.main import app
from devboard.db.repositories import (
    ContextProviderResourceRepository,
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
        )
        db_session.commit()

        response = client.get(f"/api/projects/{created_project.id}/resources")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_project_resources_with_data(self, client, db_session, test_project_data, test_resource_data):
        """Test listing project resources with existing data."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
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
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
        )
        db_session.commit()

        response = client.get(f"/api/projects/{created_project.id}/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_project_tasks_with_data(self, client, db_session, test_project_data, test_task_data):
        """Test listing project tasks with existing data."""
        # Create test project
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(
            name=test_project_data["name"], description=test_project_data["description"]
        )
        db_session.commit()

        # Create test tasks
        task_repo = TaskRepository(db_session)
        task_repo.create(project_id=created_project.id, title="Task 1", status=test_task_data["status"])
        task_repo.create(project_id=created_project.id, title="Task 2", status=test_task_data["status"])
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


class TestProjectAgentEndpoints:
    """Test project agent API endpoints."""

    @pytest.fixture
    def mock_project_agent(self):
        """Mock project agent."""
        mock_agent = Mock()
        mock_agent.run = AsyncMock()

        # Create proper mock responses with new_messages() method
        def create_mock_result(message_text):
            mock_result = Mock(spec=AgentRunResult)
            mock_result.output = message_text

            # Mock the new_messages() method to return a list containing the response
            mock_response = ModelResponse(parts=[TextPart(content=message_text)])
            mock_result.new_messages = Mock(return_value=[mock_response])

            return mock_result

        mock_message_result = create_mock_result(
            "I can help you analyze your project and answer questions about your codebase, GitHub repositories, and Jira issues."
        )

        mock_tool_approval_result = create_mock_result(
            "Great! I've processed your tool approvals and retrieved the requested information."
        )

        # Set return value based on whether it's a string prompt or tool approvals
        def run_side_effect(prompt_or_approvals, message_history, deps):
            if isinstance(prompt_or_approvals, str):
                return mock_message_result
            else:  # DeferredToolApprovalResult
                return mock_tool_approval_result

        mock_agent.run.side_effect = run_side_effect

        return mock_agent

    @pytest.fixture
    def client_with_mock_project_agent(self, client, mock_project_agent):
        """Test client with mocked project agent."""
        # Override the dependency
        app.dependency_overrides[get_project_agent] = lambda: mock_project_agent

        yield client

        # Clean up override
        if get_project_agent in app.dependency_overrides:
            del app.dependency_overrides[get_project_agent]

    @pytest.fixture
    def test_project_with_data(self, db_session):
        """Create a test project for agent tests."""
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")
        db_session.commit()
        return created_project

    def test_send_project_conversation_message(
        self, client_with_mock_project_agent, test_project_with_data, mock_project_agent
    ):
        """Test sending a message to the project agent."""
        project = test_project_with_data

        message_request = {"message": "What GitHub repositories are connected to this project?"}

        response = client_with_mock_project_agent.post(
            f"/api/projects/{project.id}/agent/messages", json=message_request
        )
        assert response.status_code == 200

        conversation_response = response.json()
        assert "type" in conversation_response
        assert conversation_response["type"] == "message"
        assert "message" in conversation_response
        assert conversation_response["message"]["role"] == "agent"
        assert "project" in conversation_response["message"]["text_content"]

        # Verify the mock agent was called correctly
        mock_project_agent.run.assert_called_once()
        args, kwargs = mock_project_agent.run.call_args
        assert kwargs["prompt_or_approvals"] == "What GitHub repositories are connected to this project?"

    def test_send_project_conversation_message_project_not_found(self, client):
        """Test sending a message for non-existent project."""
        message_request = {"message": "Test message"}
        response = client.post("/api/projects/999/agent/messages", json=message_request)
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"

    def test_approve_project_tools(self, client_with_mock_project_agent, test_project_with_data, mock_project_agent):
        """Test approving tool calls from the project agent."""
        project = test_project_with_data

        # First, send a message that would trigger a tool call to create conversation history
        from unittest.mock import Mock

        from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, UserPromptPart
        from pydantic_ai.tools import DeferredToolRequests

        # Mock the agent to return a tool request first, then tool approval result
        def mock_run_side_effect(*args, **kwargs):
            prompt_or_approvals = kwargs.get("prompt_or_approvals")
            if isinstance(prompt_or_approvals, str):
                # First call - return tool request
                tool_call_part = ToolCallPart(tool_name="fetch_github_issues", tool_call_id="test_call_1", args={})

                mock_result = Mock(spec=AgentRunResult)
                mock_result.output = DeferredToolRequests(approvals=[tool_call_part])
                mock_result.new_messages = Mock(
                    return_value=[
                        ModelRequest(parts=[UserPromptPart(content="Fetch GitHub issues")]),
                        ModelResponse(parts=[tool_call_part]),
                    ]
                )
                return mock_result
            else:
                # Second call - return approval result
                mock_result = Mock(spec=AgentRunResult)
                mock_result.output = (
                    "Great! I've processed your tool approvals and retrieved the requested information."
                )
                mock_result.new_messages = Mock(
                    return_value=[
                        ModelResponse(
                            parts=[
                                TextPart(
                                    content="Great! I've processed your tool approvals and retrieved the requested information."
                                )
                            ]
                        )
                    ]
                )
                return mock_result

        mock_project_agent.run.side_effect = mock_run_side_effect

        # Step 1: Send a message that triggers a tool call
        message_request = {"message": "Can you fetch the GitHub issues for this project?"}
        response1 = client_with_mock_project_agent.post(
            f"/api/projects/{project.id}/agent/messages", json=message_request
        )
        assert response1.status_code == 200
        assert response1.json()["type"] == "tool_request"

        # Step 2: Now approve the tool call
        approval_request = {
            "approvals": {"test_call_1": {"approved": True, "feedback": "Go ahead and fetch the GitHub issues"}}
        }

        response = client_with_mock_project_agent.post(
            f"/api/projects/{project.id}/agent/approve-tools", json=approval_request
        )
        assert response.status_code == 200

        conversation_response = response.json()
        assert "type" in conversation_response
        assert conversation_response["type"] == "message"
        assert "message" in conversation_response
        assert conversation_response["message"]["role"] == "agent"
        assert "tool approvals" in conversation_response["message"]["text_content"]

        # Verify the mock agent was called twice (message + approval)
        assert mock_project_agent.run.call_count == 2

        # Check the second call was with tool approvals
        second_call_kwargs = mock_project_agent.run.call_args_list[1][1]
        assert not isinstance(second_call_kwargs["prompt_or_approvals"], str)

    def test_approve_project_tools_project_not_found(self, client):
        """Test tool approval for non-existent project."""
        approval_request = {"approvals": {"test_call_1": {"approved": True}}}
        response = client.post("/api/projects/999/agent/approve-tools", json=approval_request)
        assert response.status_code == 404
        assert response.json()["detail"] == "Project not found"
