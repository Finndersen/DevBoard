"""Tests for context assembly service."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from devboard.context_providers.base import (
    BaseContextProvider,
    ContextStrategy,
)
from devboard.context_providers.registry import ContextProviderRegistry
from devboard.db.models import ContextProviderResource, Project
from devboard.db.repositories import ContextProviderResourceRepository, ProjectRepository
from devboard.services.context_assembly import (
    ContextAssemblyService,
    ProjectContextData,
)


class MockTestProvider(BaseContextProvider):
    """Mock provider for testing."""

    provider_type = "test"

    def __init__(self, can_handle_uris=None, strategy=ContextStrategy.EAGER, resource_data=None):
        self.can_handle_uris = can_handle_uris or []
        self.strategy = strategy
        self.resource_data = resource_data or {}
        self.get_resource = AsyncMock(return_value=self.resource_data)
        self.generate_resource_description = AsyncMock(return_value="Mock description")
        self.get_relevant_context = AsyncMock(return_value="Mock context")

    @classmethod
    def create_instance(cls):
        return cls()

    @classmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        # Default behavior for tests - override in specific instances
        return "github.com" in resource_uri or resource_uri.startswith("test://")

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        return self.strategy

    async def get_resource(self, resource_uri: str):
        return self.resource_data

    async def generate_resource_description(self, resource_uri: str) -> str:
        return "Mock description"

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        return "Mock context"


class MockTest1Provider(BaseContextProvider):
    """First mock provider for multi-provider tests."""

    provider_type = "test1"

    @classmethod
    def create_instance(cls):
        return cls()

    @classmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        return True

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        return ContextStrategy.EAGER

    async def get_resource(self, resource_uri: str):
        return {}

    async def generate_resource_description(self, resource_uri: str) -> str:
        return "Test1 description"

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        return "Test1 context"


class MockTest2Provider(BaseContextProvider):
    """Second mock provider for multi-provider tests."""

    provider_type = "test2"

    @classmethod
    def create_instance(cls):
        return cls()

    @classmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        return True

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        return ContextStrategy.EAGER

    async def get_resource(self, resource_uri: str):
        return {}

    async def generate_resource_description(self, resource_uri: str) -> str:
        return "Test2 description"

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        return "Test2 context"


class MockGitHubProvider(BaseContextProvider):
    """Mock GitHub provider for auto-detection tests."""

    provider_type = "github"

    @classmethod
    def create_instance(cls):
        return cls()

    @classmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        return "github.com" in resource_uri

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        return ContextStrategy.EAGER

    async def get_resource(self, resource_uri: str):
        return {"data": "pr_data"}

    async def generate_resource_description(self, resource_uri: str) -> str:
        return "GitHub resource description"

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        return "GitHub context"


class MockOnDemandProvider(BaseContextProvider):
    """Mock provider that always uses ON_DEMAND strategy."""

    provider_type = "test_on_demand"

    @classmethod
    def create_instance(cls):
        return cls()

    @classmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        return resource_uri.startswith("test://")

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        return ContextStrategy.ON_DEMAND

    async def get_resource(self, resource_uri: str):
        return {}

    async def generate_resource_description(self, resource_uri: str) -> str:
        return "Auto-generated description"

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        return "Relevant context"


class TestContextAssemblyService:
    """Test context assembly service."""

    def setup_method(self):
        """Clear registry before each test."""
        ContextProviderRegistry.clear()

    @pytest.fixture
    def mock_project_repo(self):
        """Mock project repository."""
        return Mock(spec=ProjectRepository)

    @pytest.fixture
    def mock_resource_repo(self):
        """Mock context provider resource repository."""
        return Mock(spec=ContextProviderResourceRepository)

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_session_factory(self, mock_db_session):
        """Mock session factory."""
        factory = Mock()

        def session_context():
            session_mock = Mock()
            session_mock.__enter__ = Mock(return_value=mock_db_session)
            session_mock.__exit__ = Mock(return_value=None)
            return session_mock

        factory.return_value = session_context()
        return factory

    @pytest.fixture
    def service(self, mock_session_factory):
        """Context assembly service with mocked DB."""
        return ContextAssemblyService(mock_session_factory)

    @pytest.fixture
    def mock_provider(self):
        """Mock context provider."""
        provider = Mock(spec=BaseContextProvider)
        provider.provider_type = "test"
        provider.can_handle_uri.return_value = True
        provider.get_retrieval_strategy.return_value = ContextStrategy.EAGER
        provider.get_resource.return_value = {"data": "test_data"}
        provider.generate_resource_description.return_value = "Test resource description"
        return provider

    def test_extract_uris_from_text(self, service):
        """Test URI extraction from text."""
        # Register a mock provider to validate URLs
        ContextProviderRegistry.register(MockTestProvider)

        text = """
        Working on https://github.com/owner/repo/pull/123 and also
        see https://github.com/owner/repo/issues/456 for details.
        Invalid URL: https://unknown.com/resource
        """

        uris = service._extract_uris_from_text(text)

        expected_uris = [
            "https://github.com/owner/repo/pull/123",
            "https://github.com/owner/repo/issues/456",
        ]
        assert set(uris) == set(expected_uris)

    def test_extract_uris_from_empty_text(self, service):
        """Test URI extraction from empty text."""
        assert service._extract_uris_from_text("") == []
        assert service._extract_uris_from_text(None) == []

    @pytest.mark.asyncio
    async def test_get_project_context_no_links(self, service, mock_db_session):
        """Test context assembly with no links."""
        project = Project(id=1, name="Test", details="No URLs here", current_status="active")

        with (
            patch(
                "devboard.services.context_assembly.ProjectRepository"
            ) as mock_project_repo_class,
            patch(
                "devboard.services.context_assembly.ContextProviderResourceRepository"
            ) as mock_resource_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_resource_repo = Mock()
            mock_resource_repo.get_resources_for_project.return_value = []
            mock_resource_repo_class.return_value = mock_resource_repo

            result = await service.get_project_context(1, "test query")

            assert isinstance(result, ProjectContextData)
            assert result.eager_context == []
            assert result.on_demand_resources == []

    @pytest.mark.asyncio
    async def test_get_project_context_with_explicit_links(
        self, service, mock_db_session, mock_provider
    ):
        """Test context assembly with explicit provider resources."""
        project = Project(id=1, name="Test", details="Project description", current_status="active")
        link = ContextProviderResource(
            resource_uri="test://resource",
            description="User provided description",
            provider_name="test",
        )

        with (
            patch(
                "devboard.services.context_assembly.ProjectRepository"
            ) as mock_project_repo_class,
            patch(
                "devboard.services.context_assembly.ContextProviderResourceRepository"
            ) as mock_resource_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_resource_repo = Mock()
            mock_resource_repo.get_resources_for_project.return_value = [link]
            mock_resource_repo_class.return_value = mock_resource_repo

            ContextProviderRegistry.register(MockTestProvider)

            result = await service.get_project_context(1, "test query")

            assert isinstance(result, ProjectContextData)
            assert len(result.eager_context) == 1
            assert result.eager_context[0].uri == "test://resource"
            assert result.eager_context[0].description == "User provided description"

    @pytest.mark.asyncio
    async def test_get_project_context_with_detected_uris(
        self, service, mock_db_session, mock_provider
    ):
        """Test context assembly with auto-detected URIs from project description."""
        project = Project(
            id=1,
            name="Test",
            details="Working on https://github.com/owner/repo/pull/123",
            current_status="active",
        )

        # Mock GitHub provider for detected URI
        github_provider = Mock(spec=BaseContextProvider)
        github_provider.provider_type = "github"
        github_provider.can_handle_uri.return_value = True
        github_provider.get_retrieval_strategy.return_value = ContextStrategy.EAGER
        github_provider.get_resource = AsyncMock(return_value={"data": "pr_data"})

        with (
            patch(
                "devboard.services.context_assembly.ProjectRepository"
            ) as mock_project_repo_class,
            patch(
                "devboard.services.context_assembly.ContextProviderResourceRepository"
            ) as mock_resource_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_resource_repo = Mock()
            mock_resource_repo.get_resources_for_project.return_value = []
            mock_resource_repo_class.return_value = mock_resource_repo

            ContextProviderRegistry.register(MockGitHubProvider)

            result = await service.get_project_context(1, "test query")

            assert isinstance(result, ProjectContextData)
            assert len(result.eager_context) == 1
            assert result.eager_context[0].uri == "https://github.com/owner/repo/pull/123"
            assert result.eager_context[0].description == "GitHub resource description"  # Generated description for auto-detected resource

    @pytest.mark.asyncio
    async def test_get_project_context_on_demand_with_user_description(
        self, service, mock_db_session
    ):
        """Test ON_DEMAND resources prioritize user descriptions."""
        project = Project(id=1, name="Test", details="Project description", current_status="active")
        link = ContextProviderResource(
            resource_uri="test://large-resource",
            description="User provided description",
            provider_name="test",
        )

        with (
            patch(
                "devboard.services.context_assembly.ProjectRepository"
            ) as mock_project_repo_class,
            patch(
                "devboard.services.context_assembly.ContextProviderResourceRepository"
            ) as mock_resource_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_resource_repo = Mock()
            mock_resource_repo.get_resources_for_project.return_value = [link]
            mock_resource_repo_class.return_value = mock_resource_repo

            ContextProviderRegistry.register(MockOnDemandProvider)

            result = await service.get_project_context(1, "test query")

            assert isinstance(result, ProjectContextData)
            assert len(result.on_demand_resources) == 1

            resource = result.on_demand_resources[0]
            assert resource.description == "User provided description"  # User description used

    @pytest.mark.asyncio
    async def test_get_project_context_on_demand_without_user_description(
        self, service, mock_db_session
    ):
        """Test ON_DEMAND resources generate descriptions when user doesn't provide one."""
        project = Project(id=1, name="Test", details="Project description", current_status="active")
        link = ContextProviderResource(
            resource_uri="test://large-resource",
            description=None,
            provider_name="test",
        )

        with (
            patch(
                "devboard.services.context_assembly.ProjectRepository"
            ) as mock_project_repo_class,
            patch(
                "devboard.services.context_assembly.ContextProviderResourceRepository"
            ) as mock_resource_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_resource_repo = Mock()
            mock_resource_repo.get_resources_for_project.return_value = [link]
            mock_resource_repo_class.return_value = mock_resource_repo

            ContextProviderRegistry.register(MockOnDemandProvider)

            result = await service.get_project_context(1, "test query")

            resource = result.on_demand_resources[0]
            assert (
                resource.description == "Auto-generated description"
            )  # Generated description used

    @pytest.mark.asyncio
    async def test_get_on_demand_context(self, service):
        """Test getting on-demand context."""
        ContextProviderRegistry.register(MockTestProvider)

        result = await service.get_on_demand_context("test://resource", "specific query")

        assert result == "Mock context"

    def test_list_available_providers(self, service):
        """Test listing available providers."""
        ContextProviderRegistry.register(MockTest1Provider)
        ContextProviderRegistry.register(MockTest2Provider)

        result = service.list_available_providers()
        assert set(result) == {"test1", "test2"}
