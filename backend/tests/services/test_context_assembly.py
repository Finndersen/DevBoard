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
        # Don't handle large-resource URIs to allow MockOnDemandProvider to handle them
        if "large-resource" in resource_uri:
            return False
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
        return resource_uri.startswith("test://") and (
            "large-resource" in resource_uri or "on-demand" in resource_uri
        )

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
    def test_registry(self):
        """Test registry with mock providers."""
        return ContextProviderRegistry(
            [
                MockOnDemandProvider,  # Put this first so it gets priority for on-demand URIs
                MockTestProvider,
                MockTest1Provider,
                MockTest2Provider,
                MockGitHubProvider,
            ],
            key_attr="provider_type",
        )

    @pytest.fixture
    def service(self, mock_session_factory, test_registry):
        """Context assembly service with mocked DB and test registry."""
        return ContextAssemblyService(mock_session_factory, test_registry)

    def test_extract_uris_from_text(self, service):
        """Test URI extraction from text."""
        text = """
        Working on https://github.com/owner/repo/pull/123 and also
        see https://github.com/owner/repo/issues/456 for details.
        Also see https://unknown.com/resource
        """

        uris = service._extract_uris_from_text(text)

        # All URLs should be extracted since test registry has providers that handle all URLs
        expected_uris = [
            "https://github.com/owner/repo/pull/123",
            "https://github.com/owner/repo/issues/456",
            "https://unknown.com/resource",
        ]
        assert set(uris) == set(expected_uris)

    def test_extract_uris_from_empty_text(self, service):
        """Test URI extraction from empty text."""
        assert service._extract_uris_from_text("") == []
        assert service._extract_uris_from_text(None) == []

    @pytest.mark.asyncio
    async def test_get_project_context_no_links(self, service, mock_db_session):
        """Test context assembly with no links."""
        # Mock the specification document
        from devboard.db.models.document import Document, DocumentType

        spec_doc = Mock(spec=Document)
        spec_doc.content = "No URLs here"
        spec_doc.document_type = DocumentType.PROJECT_SPECIFICATION

        project = Project(
            id=1, name="Test", description="Project description", specification_document_id=1
        )
        project.specification = spec_doc

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
    async def test_get_project_context_with_explicit_links(self, service, mock_db_session):
        """Test context assembly with explicit provider resources."""
        # Mock the specification document
        from devboard.db.models.document import Document, DocumentType

        spec_doc = Mock(spec=Document)
        spec_doc.content = "Project description"
        spec_doc.document_type = DocumentType.PROJECT_SPECIFICATION

        project = Project(
            id=1, name="Test", description="Project description", specification_document_id=1
        )
        project.specification = spec_doc
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

            result = await service.get_project_context(1, "test query")

            assert isinstance(result, ProjectContextData)
            assert len(result.eager_context) == 1
            assert result.eager_context[0].uri == "test://resource"
            assert result.eager_context[0].description == "User provided description"

    @pytest.mark.asyncio
    async def test_get_project_context_with_detected_uris(self, service, mock_db_session):
        """Test context assembly with auto-detected URIs from project description."""
        # Mock the specification document
        from devboard.db.models.document import Document, DocumentType

        spec_doc = Mock(spec=Document)
        spec_doc.content = "Working on https://github.com/owner/repo/pull/123"
        spec_doc.document_type = DocumentType.PROJECT_SPECIFICATION

        project = Project(
            id=1,
            name="Test",
            description="Working on https://github.com/owner/repo/pull/123",
            specification_document_id=1,
        )
        project.specification = spec_doc

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
            assert len(result.eager_context) == 1
            assert result.eager_context[0].uri == "https://github.com/owner/repo/pull/123"
            assert (
                result.eager_context[0].description == "GitHub resource description"
                or result.eager_context[0].description == "Mock description"
            )  # Generated description for auto-detected resource

    @pytest.mark.asyncio
    async def test_get_project_context_on_demand_with_user_description(
        self, service, mock_db_session
    ):
        """Test ON_DEMAND resources prioritize user descriptions."""
        # Mock the specification document
        from devboard.db.models.document import Document, DocumentType

        spec_doc = Mock(spec=Document)
        spec_doc.content = "Project description"
        spec_doc.document_type = DocumentType.PROJECT_SPECIFICATION

        project = Project(
            id=1, name="Test", description="Project description", specification_document_id=1
        )
        project.specification = spec_doc
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
        # Mock the specification document
        from devboard.db.models.document import Document, DocumentType

        spec_doc = Mock(spec=Document)
        spec_doc.content = "Project description"
        spec_doc.document_type = DocumentType.PROJECT_SPECIFICATION

        project = Project(
            id=1, name="Test", description="Project description", specification_document_id=1
        )
        project.specification = spec_doc
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

            result = await service.get_project_context(1, "test query")

            resource = result.on_demand_resources[0]
            assert (
                resource.description == "Auto-generated description"
            )  # Generated description used

    @pytest.mark.asyncio
    async def test_get_on_demand_context(self, service):
        """Test getting on-demand context."""

        result = await service.get_on_demand_context("test://resource", "specific query")

        assert result == "Mock context"

    def test_list_available_providers(self, service):
        """Test listing available providers."""

        result = service.list_available_providers()
        expected_providers = {"test", "test1", "test2", "github", "test_on_demand"}
        assert set(result) == expected_providers
