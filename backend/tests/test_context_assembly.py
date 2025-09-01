"""Tests for context assembly service."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from devboard.context_providers.base import (
    BaseContextProvider,
    ContextProviderRegistry,
    ContextStrategy,
)
from devboard.db.models import ContextProviderLink, Project
from devboard.repositories.context_provider_link import ContextProviderLinkRepository
from devboard.repositories.project import ProjectRepository
from devboard.services.context_assembly import (
    ContextAssemblyService,
    ProjectContextData,
    ResourceValidationResult,
)


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
    def mock_link_repo(self):
        """Mock context provider link repository."""
        return Mock(spec=ContextProviderLinkRepository)

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
        mock_provider = Mock(spec=BaseContextProvider)
        mock_provider.can_handle_uri.side_effect = lambda uri: "github.com" in uri
        ContextProviderRegistry.register("test", mock_provider)

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
                "devboard.services.context_assembly.ContextProviderLinkRepository"
            ) as mock_link_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_link_repo = Mock()
            mock_link_repo.get_by_parent.return_value = []
            mock_link_repo_class.return_value = mock_link_repo

            result = await service.get_project_context(1, "test query")

            assert isinstance(result, ProjectContextData)
            assert result.eager_context == []
            assert result.on_demand_resources == []

    @pytest.mark.asyncio
    async def test_get_project_context_with_explicit_links(
        self, service, mock_db_session, mock_provider
    ):
        """Test context assembly with explicit provider links."""
        project = Project(id=1, name="Test", details="Project description", current_status="active")
        link = ContextProviderLink(
            parent_id=1,
            parent_type="project",
            resource_uri="test://resource",
            description="User provided description",
        )

        with (
            patch(
                "devboard.services.context_assembly.ProjectRepository"
            ) as mock_project_repo_class,
            patch(
                "devboard.services.context_assembly.ContextProviderLinkRepository"
            ) as mock_link_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_link_repo = Mock()
            mock_link_repo.get_by_parent.return_value = [link]
            mock_link_repo_class.return_value = mock_link_repo

            ContextProviderRegistry.register("test", mock_provider)

            result = await service.get_project_context(1, "test query")

            assert isinstance(result, ProjectContextData)
            assert len(result.eager_context) == 1
            assert result.eager_context[0].uri == "test://resource"
            assert result.eager_context[0].user_description == "User provided description"

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
                "devboard.services.context_assembly.ContextProviderLinkRepository"
            ) as mock_link_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_link_repo = Mock()
            mock_link_repo.get_by_parent.return_value = []
            mock_link_repo_class.return_value = mock_link_repo

            ContextProviderRegistry.register("github", github_provider)

            result = await service.get_project_context(1, "test query")

            assert isinstance(result, ProjectContextData)
            assert len(result.eager_context) == 1
            assert result.eager_context[0].uri == "https://github.com/owner/repo/pull/123"
            assert (
                result.eager_context[0].user_description is None
            )  # Auto-detected, no user description

    @pytest.mark.asyncio
    async def test_get_project_context_on_demand_with_user_description(
        self, service, mock_db_session
    ):
        """Test ON_DEMAND resources prioritize user descriptions."""
        project = Project(id=1, name="Test", details="Project description", current_status="active")
        link = ContextProviderLink(
            parent_id=1,
            parent_type="project",
            resource_uri="test://large-resource",
            description="User provided description",
        )

        # Mock provider that returns ON_DEMAND strategy
        provider = Mock(spec=BaseContextProvider)
        provider.provider_type = "test"
        provider.can_handle_uri.return_value = True
        provider.get_retrieval_strategy.return_value = ContextStrategy.ON_DEMAND
        provider.generate_resource_description = AsyncMock(
            return_value="Auto-generated description"
        )

        with (
            patch(
                "devboard.services.context_assembly.ProjectRepository"
            ) as mock_project_repo_class,
            patch(
                "devboard.services.context_assembly.ContextProviderLinkRepository"
            ) as mock_link_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_link_repo = Mock()
            mock_link_repo.get_by_parent.return_value = [link]
            mock_link_repo_class.return_value = mock_link_repo

            ContextProviderRegistry.register("test", provider)

            result = await service.get_project_context(1, "test query")

            assert isinstance(result, ProjectContextData)
            assert len(result.on_demand_resources) == 1

            resource = result.on_demand_resources[0]
            assert resource.description == "User provided description"  # User description used
            assert resource.has_user_description is True
            # generate_resource_description should NOT be called when user description exists
            provider.generate_resource_description.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_project_context_on_demand_without_user_description(
        self, service, mock_db_session
    ):
        """Test ON_DEMAND resources generate descriptions when user doesn't provide one."""
        project = Project(id=1, name="Test", details="Project description", current_status="active")
        link = ContextProviderLink(
            parent_id=1,
            parent_type="project",
            resource_uri="test://large-resource",
            description=None,  # No user description
        )

        provider = Mock(spec=BaseContextProvider)
        provider.provider_type = "test"
        provider.can_handle_uri.return_value = True
        provider.get_retrieval_strategy.return_value = ContextStrategy.ON_DEMAND
        provider.generate_resource_description = AsyncMock(
            return_value="Auto-generated description"
        )

        with (
            patch(
                "devboard.services.context_assembly.ProjectRepository"
            ) as mock_project_repo_class,
            patch(
                "devboard.services.context_assembly.ContextProviderLinkRepository"
            ) as mock_link_repo_class,
        ):
            mock_project_repo = Mock()
            mock_project_repo.get_by_id.return_value = project
            mock_project_repo_class.return_value = mock_project_repo

            mock_link_repo = Mock()
            mock_link_repo.get_by_parent.return_value = [link]
            mock_link_repo_class.return_value = mock_link_repo

            ContextProviderRegistry.register("test", provider)

            result = await service.get_project_context(1, "test query")

            resource = result.on_demand_resources[0]
            assert (
                resource.description == "Auto-generated description"
            )  # Generated description used
            assert resource.has_user_description is False
            provider.generate_resource_description.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_resource_uri_valid(self, service):
        """Test resource validation for valid URI."""
        provider = Mock(spec=BaseContextProvider)
        provider.provider_type = "test"
        provider.can_handle_uri.return_value = True
        provider.get_retrieval_strategy.return_value = ContextStrategy.EAGER
        provider.generate_resource_description = AsyncMock(return_value="Test description")

        ContextProviderRegistry.register("test", provider)

        result = await service.validate_resource_uri("test://resource")

        assert isinstance(result, ResourceValidationResult)
        assert result.valid is True
        assert result.provider_type == "test"
        assert result.strategy == "EAGER"
        assert result.description == "Test description"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_validate_resource_uri_no_provider(self, service):
        """Test resource validation for URI with no provider."""
        result = await service.validate_resource_uri("unknown://resource")

        assert isinstance(result, ResourceValidationResult)
        assert result.valid is False
        assert result.error == "No provider found for this URI type"

    @pytest.mark.asyncio
    async def test_get_on_demand_context(self, service):
        """Test getting on-demand context."""
        provider = Mock(spec=BaseContextProvider)
        provider.get_relevant_context = AsyncMock(return_value="Relevant context")

        ContextProviderRegistry.register("test", provider)

        result = await service.get_on_demand_context("test://resource", "specific query")

        assert result == "Relevant context"
        provider.get_relevant_context.assert_called_once_with("test://resource", "specific query")

    def test_list_available_providers(self, service):
        """Test listing available providers."""
        provider1 = Mock(spec=BaseContextProvider)
        provider2 = Mock(spec=BaseContextProvider)

        ContextProviderRegistry.register("test1", provider1)
        ContextProviderRegistry.register("test2", provider2)

        result = service.list_available_providers()
        assert set(result) == {"test1", "test2"}
