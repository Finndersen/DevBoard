"""Tests for Q&A router endpoints."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from devboard.agents.project_agent import QAAgentService
from devboard.context_providers import ContextStrategy
from devboard.db.models import Project
from devboard.services.context_assembly import (
    EagerContextData,
    NoProviderFound,
    OnDemandResourceInfo,
    ProjectContextData,
    ResourceInfo,
)


@pytest.fixture
def sample_project():
    """Sample project for testing."""
    return Project(
        id=1,
        name="Test Project",
        details="Test project description with https://github.com/owner/repo/pull/123",
        current_status="active",
    )


@pytest.fixture
def sample_context_data():
    """Sample context data for testing."""
    return ProjectContextData(
        eager_context=[
            EagerContextData(
                uri="https://github.com/owner/repo/pull/123",
                description="Important PR",
                provider_type="github",
                data={"title": "Fix bug", "body": "Bug fix details"},
            )
        ],
        on_demand_resources=[
            OnDemandResourceInfo(
                uri="https://github.com/owner/repo",
                description="Main repository",
                provider_type="github",
                has_user_description=True,
            )
        ],
        provider_errors=[],
    )


class TestChatEndpoint:
    """Test the project chat endpoint."""

    @patch("devboard.api.routers.qa.qa_agent_service")
    def test_chat_with_project_success(self, mock_qa_service, client, db_session, sample_project):
        """Test successful chat with project."""
        # Add project to database
        db_session.add(sample_project)
        db_session.commit()

        # Setup mock service
        mock_qa_service.chat = AsyncMock(return_value="AI response to query")

        # Make request
        response = client.post(
            "/api/projects/1/chat", json={"query": "What is this project about?"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "AI response to query"
        assert data["project_id"] == 1

        # Verify service was called correctly
        mock_qa_service.chat.assert_called_once_with(1, "What is this project about?")

    def test_chat_with_nonexistent_project(self, client):
        """Test chat with non-existent project."""
        response = client.post("/api/projects/999/chat", json={"query": "test query"})

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    @patch("devboard.api.routers.qa.qa_agent_service")
    def test_chat_service_error(self, mock_qa_service, client, db_session, sample_project):
        """Test chat endpoint when service raises error."""
        # Add project to database
        db_session.add(sample_project)
        db_session.commit()

        # Setup mock service to raise error
        mock_qa_service.chat = AsyncMock(side_effect=Exception("Service error"))

        response = client.post("/api/projects/1/chat", json={"query": "test query"})

        assert response.status_code == 500
        assert "Chat processing failed" in response.json()["detail"]


class TestContextEndpoint:
    """Test the project context endpoint."""

    @patch("devboard.api.routers.qa.qa_agent_service")
    def test_get_project_context_success(
        self, mock_qa_service, client, db_session, sample_project, sample_context_data
    ):
        """Test successful context retrieval."""
        # Add project to database
        db_session.add(sample_project)
        db_session.commit()

        # Setup mock service
        mock_qa_service.context_service.get_project_context = AsyncMock(
            return_value=sample_context_data
        )

        response = client.get("/api/projects/1/context?query=test")

        assert response.status_code == 200
        data = response.json()

        assert data["project_id"] == 1
        assert data["project_name"] == "Test Project"
        assert data["query"] == "test"

        # Check eager context structure
        assert len(data["eager_context"]) == 1
        eager_ctx = data["eager_context"][0]
        assert eager_ctx["uri"] == "https://github.com/owner/repo/pull/123"
        assert eager_ctx["user_description"] == "Important PR"
        assert eager_ctx["provider_type"] == "github"
        assert eager_ctx["data"] == {"title": "Fix bug", "body": "Bug fix details"}

        # Check on_demand resources structure
        assert len(data["on_demand_resources"]) == 1
        on_demand = data["on_demand_resources"][0]
        assert on_demand["uri"] == "https://github.com/owner/repo"
        assert on_demand["description"] == "Main repository"
        assert on_demand["provider_type"] == "github"
        assert on_demand["has_user_description"] is True

        # Verify service was called correctly
        mock_qa_service.context_service.get_project_context.assert_called_once_with(1, "test")

    def test_get_project_context_nonexistent_project(self, client):
        """Test context endpoint with non-existent project."""
        response = client.get("/api/projects/999/context")

        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]


class TestValidateResourceEndpoint:
    """Test the resource validation endpoint."""

    @patch("devboard.api.routers.qa.qa_agent_service")
    def test_validate_resource_success(self, mock_qa_service, client):
        """Test successful resource validation."""
        uri = "https://github.com/owner/repo/pull/123"
        mock_result = ResourceInfo(
            provider=MagicMock(provider_type="github"),
            retrieval_strategy=ContextStrategy.EAGER,
            description="Test PR description",
            uri=uri,
        )
        mock_qa_service.context_service.get_resource_info = AsyncMock(return_value=mock_result)

        response = client.post(
            "/api/projects/validate-resource",
            params={"resource_uri": uri},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["resource_uri"] == uri
        assert data["valid"] is True
        assert data["provider_type"] == "github"
        assert data["strategy"] == "EAGER"
        assert data["description"] == "Test PR description"
        assert data["error"] is None

    @patch("devboard.api.routers.qa.qa_agent_service")
    def test_validate_resource_invalid(self, mock_qa_service, client):
        """Test validation of invalid resource."""

        mock_qa_service.context_service.get_resource_info = AsyncMock(
            side_effect=NoProviderFound("No provider found for this URI type")
        )
        response = client.post(
            "/api/projects/validate-resource", params={"resource_uri": "invalid://resource"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["valid"] is False
        assert data["error"] == "No provider found for this URI type"


class TestQAAgentService:
    """Test Q&A agent service integration."""

    @pytest.fixture
    def mock_context_service(self):
        """Mock context assembly service."""
        service = Mock()
        service.get_project_context = AsyncMock(
            return_value=ProjectContextData(
                eager_context=[], on_demand_resources=[], provider_errors=[]
            )
        )
        service.validate_resource_uri = AsyncMock()
        return service

    @pytest.fixture
    def mock_agent(self):
        """Mock PydanticAI agent."""
        agent = Mock()
        result_mock = Mock()
        result_mock.data = "Agent response"
        agent.run = AsyncMock(return_value=result_mock)
        return agent

    @patch("devboard.services.qa_agent.Agent")
    def test_qa_agent_initialization(self, mock_agent_class, mock_context_service):
        """Test Q&A agent service initialization."""
        mock_agent_class.return_value = Mock()

        service = QAAgentService(mock_context_service)

        assert service.context_service == mock_context_service
        assert service.agent is not None
        mock_agent_class.assert_called_once()

    @pytest.mark.asyncio
    @patch("devboard.services.qa_agent.Agent")
    async def test_chat_success(self, mock_agent_class, mock_context_service, mock_agent):
        """Test successful chat processing."""
        mock_agent_class.return_value = mock_agent

        service = QAAgentService(mock_context_service)

        result = await service.chat(1, "test query")

        assert result == "Agent response"
        mock_context_service.get_project_context.assert_called_once_with(1, "test query")
        mock_agent.run.assert_called_once()

    @pytest.mark.asyncio
    @patch("devboard.services.qa_agent.Agent")
    async def test_chat_context_error(self, mock_agent_class, mock_context_service):
        """Test chat when context assembly fails."""
        mock_agent_class.return_value = Mock()
        mock_context_service.get_project_context.side_effect = Exception("Context error")

        service = QAAgentService(mock_context_service)

        result = await service.chat(1, "test query")

        assert "error processing your query" in result
        assert "Context error" in result
