"""Context assembly service for orchestrating multi-source context gathering."""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from devboard.context_providers.base import (
    BaseContextProvider,
    ContextProviderRegistry,
    ContextStrategy,
)
from devboard.db.database import SessionLocal
from devboard.db.models import ContextProviderLink
from devboard.repositories.context_provider_link import ContextProviderLinkRepository
from devboard.repositories.project import ProjectRepository

logger = logging.getLogger(__name__)


@dataclass
class EagerContextData:
    """Context data for EAGER resources that are fully loaded."""

    uri: str
    user_description: str | None
    provider_type: str
    data: dict[str, Any]


@dataclass
class OnDemandResourceInfo:
    """Information about ON_DEMAND resources available for querying."""

    uri: str
    description: str  # Primary description (user-provided or auto-generated)
    provider_type: str
    has_user_description: bool  # Indicates if description came from user


@dataclass
class ProjectContextData:
    """Complete assembled context for a project."""

    eager_context: list[EagerContextData]
    on_demand_resources: list[OnDemandResourceInfo]


@dataclass
class ResourceValidationResult:
    """Result of validating a resource URI."""

    valid: bool
    provider_type: str | None = None
    strategy: str | None = None
    description: str | None = None
    error: str | None = None


class ContextAssemblyService:
    """Service for assembling context from multiple providers based on strategies."""

    def __init__(self, db_session_factory=SessionLocal):
        self.db_session_factory = db_session_factory

    def _extract_uris_from_text(self, text: str) -> list[str]:
        """Extract potential resource URIs from text.

        Looks for URLs that might be handled by registered context providers.
        """
        if not text:
            return []

        # Pattern to match common URL formats
        url_pattern = r'https?://[^\s<>"\'{}\[\]|\\^`]+'

        urls = re.findall(url_pattern, text)

        # Filter to only URLs that have registered providers
        valid_uris = []
        for url in urls:
            if ContextProviderRegistry.get_provider_for_uri(url):
                valid_uris.append(url)

        return valid_uris

    async def get_project_context(self, project_id: int, query: str) -> ProjectContextData:
        """Assemble complete context for a project query.

        Args:
            project_id: The project to get context for
            query: The user's query that drives context selection

        Returns:
            ProjectContextData containing EAGER context data and ON_DEMAND resource descriptions
        """
        try:
            # Get project and its context provider links
            with self.db_session_factory() as db:
                project_repo = ProjectRepository(db)
                link_repo = ContextProviderLinkRepository(db)

                project = project_repo.get_by_id(project_id)
                if not project:
                    raise ValueError(f"Project {project_id} not found")

                links = link_repo.get_by_parent(project_id, "project")

            # Extract URIs from project description
            detected_uris = self._extract_uris_from_text(project.details)

            # Combine explicit links with detected URIs
            all_resource_uris = []
            explicit_uris = {link.resource_uri for link in links}

            # Add explicit links
            for link in links:
                all_resource_uris.append((link.resource_uri, link.description))

            # Add detected URIs (only small-scope ones suitable for EAGER loading)
            for uri in detected_uris:
                if uri not in explicit_uris:  # Avoid duplicates
                    provider = ContextProviderRegistry.get_provider_for_uri(uri)
                    if provider:
                        try:
                            strategy = provider.get_retrieval_strategy(uri)
                            if (
                                strategy == ContextStrategy.EAGER
                            ):  # Only include small-scope resources
                                all_resource_uris.append(
                                    (uri, None)
                                )  # No user description for auto-detected
                                logger.info(
                                    f"Auto-detected EAGER resource from project description: {uri}"
                                )
                        except Exception as e:
                            logger.warning(f"Failed to check strategy for detected URI {uri}: {e}")

            if not all_resource_uris:
                logger.info(f"No context resources found for project {project_id}")
                return ProjectContextData(eager_context=[], on_demand_resources=[])

            # Categorize resources by strategy
            eager_resources = []
            on_demand_resources = []

            for resource_uri, user_description in all_resource_uris:
                provider = ContextProviderRegistry.get_provider_for_uri(resource_uri)
                if not provider:
                    logger.warning(f"No provider found for URI: {resource_uri}")
                    continue

                try:
                    strategy = provider.get_retrieval_strategy(resource_uri)

                    if strategy == ContextStrategy.EAGER:
                        # Create a mock link object for EAGER processing
                        class MockLink:
                            def __init__(self, uri: str, desc: str | None):
                                self.resource_uri = uri
                                self.description = desc

                        mock_link = MockLink(resource_uri, user_description)
                        eager_resources.append((provider, mock_link))
                    else:
                        # Use user description if available, otherwise generate one
                        if user_description:
                            description = user_description
                            has_user_description = True
                        else:
                            description = await provider.generate_resource_description(resource_uri)
                            has_user_description = False

                        on_demand_resources.append(
                            OnDemandResourceInfo(
                                uri=resource_uri,
                                description=description,
                                provider_type=provider.provider_type,
                                has_user_description=has_user_description,
                            )
                        )
                except Exception as e:
                    logger.error(f"Error processing resource {resource_uri}: {e}")
                    continue

            # Load EAGER context in parallel
            eager_context = []
            if eager_resources:
                eager_tasks = [
                    self._load_eager_context(provider, link) for provider, link in eager_resources
                ]
                eager_results = await asyncio.gather(*eager_tasks, return_exceptions=True)

                for result in eager_results:
                    if isinstance(result, Exception):
                        logger.error(f"Error loading eager context: {result}")
                    else:
                        eager_context.append(result)

            return ProjectContextData(
                eager_context=eager_context, on_demand_resources=on_demand_resources
            )

        except Exception as e:
            logger.error(f"Error assembling context for project {project_id}: {e}")
            raise

    async def _load_eager_context(
        self, provider: BaseContextProvider, link: ContextProviderLink
    ) -> EagerContextData:
        """Load EAGER context for a single resource."""
        try:
            resource_data = await provider.get_resource(link.resource_uri)
            return EagerContextData(
                uri=link.resource_uri,
                user_description=link.description,
                provider_type=provider.provider_type,
                data=resource_data,
            )
        except Exception as e:
            logger.error(f"Error loading eager context for {link.resource_uri}: {e}")
            raise

    async def get_on_demand_context(self, resource_uri: str, query: str) -> str:
        """Get ON_DEMAND context for a specific resource and query.

        This is called by the Q&A agent when it needs specific context.

        Args:
            resource_uri: The resource to query
            query: The specific query for focused context extraction

        Returns:
            Focused context summary relevant to the query
        """
        try:
            provider = ContextProviderRegistry.get_provider_for_uri(resource_uri)
            if not provider:
                raise ValueError(f"No provider found for URI: {resource_uri}")

            return await provider.get_relevant_context(resource_uri, query)

        except Exception as e:
            logger.error(f"Error getting on-demand context for {resource_uri}: {e}")
            raise

    async def validate_resource_uri(self, resource_uri: str) -> ResourceValidationResult:
        """Validate a resource URI and return provider info.

        Args:
            resource_uri: The URI to validate

        Returns:
            ResourceValidationResult with validation results and provider information
        """
        try:
            provider = ContextProviderRegistry.get_provider_for_uri(resource_uri)
            if not provider:
                return ResourceValidationResult(
                    valid=False, error="No provider found for this URI type"
                )

            try:
                strategy = provider.get_retrieval_strategy(resource_uri)
                description = await provider.generate_resource_description(resource_uri)

                return ResourceValidationResult(
                    valid=True,
                    provider_type=provider.provider_type,
                    strategy=strategy.value,
                    description=description,
                )
            except Exception as e:
                return ResourceValidationResult(
                    valid=False, error=f"Provider validation failed: {e}"
                )

        except Exception as e:
            logger.error(f"Error validating resource URI {resource_uri}: {e}")
            return ResourceValidationResult(valid=False, error=f"Validation error: {e}")

    def list_available_providers(self) -> list[str]:
        """List all available context provider types."""
        return ContextProviderRegistry.list_available()


# Global context assembly service instance
context_assembly_service = ContextAssemblyService()
