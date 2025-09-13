"""Context assembly service for orchestrating multi-source context gathering."""

import asyncio
import logging
import re
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

import logfire

from devboard.context_providers.base import (
    BaseContextProvider,
    ContextProviderUnavailable,
    ContextStrategy,
)
from devboard.context_providers.registry import (
    ContextProviderRegistry,
    context_provider_registry,
)
from devboard.db.database import SessionLocal, SessionMakerType
from devboard.db.repositories import (
    ContextProviderResourceRepository,
    ProjectRepository,
)

logger = logging.getLogger(__name__)


class NoProviderFound(Exception):
    """No provider found for the given resource URI."""


@dataclass
class EagerContextData:
    """Context data for EAGER resources that are fully loaded."""

    uri: str
    description: str | None
    provider_type: str
    data: dict[str, Any]


@dataclass
class OnDemandResourceInfo:
    """Information about ON_DEMAND resources available for querying."""

    uri: str
    description: str  # Primary description (user-provided or auto-generated)
    provider_type: str
    has_user_description: bool  # True if description was user-provided, False if auto-generated


@dataclass
class ResourceInfo:
    uri: str
    description: str
    provider: BaseContextProvider  # TODO: Maybe not ideal having this here?
    retrieval_strategy: ContextStrategy


@dataclass
class ResourceRetrievalError:
    """Information about a provider error."""

    resource_uri: str
    error_message: str


@dataclass
class ProjectContextData:
    """Complete assembled context for a project."""

    eager_context: list[EagerContextData]
    on_demand_resources: list[OnDemandResourceInfo]
    provider_errors: list[ResourceRetrievalError]


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

    def __init__(
        self,
        db_session_factory: SessionMakerType = SessionLocal,
        context_provider_registry_instance: ContextProviderRegistry | None = None,
    ):
        self.db_session_factory = db_session_factory
        self.context_provider_registry = (
            context_provider_registry_instance or context_provider_registry
        )

    def _get_provider_instance(
        self, resource_uri: str
    ) -> tuple[BaseContextProvider | None, str | None]:
        """Get provider instance for a resource URI.

        Args:
            resource_uri: The URI to find a provider for

        Returns:
            Tuple of (provider_instance, error_message). If provider_instance is None,
            error_message will contain the reason why.
        """
        provider_class = self.context_provider_registry.get_provider_for_uri(resource_uri)
        if not provider_class:
            return None, "No provider found for this URI type"

        try:
            provider = provider_class.create_instance()
            return provider, None
        except ContextProviderUnavailable as e:
            return None, str(e)

    def _extract_uris_from_text(self, text: str) -> list[str]:
        """Extract potential resource URIs from text.

        Looks for URLs that might be handled by registered context providers.
        """
        if not text:
            return []

        # Pattern to match common URL formats
        url_pattern = r'https?://[^\s<>"\'{}\[\]|\\^`]+'

        urls: list[str] = re.findall(url_pattern, text)

        # Filter to only URLs that have registered providers
        valid_uris: list[str] = []
        for url in urls:
            provider_or_class = self.context_provider_registry.get_provider_for_uri(url)
            if provider_or_class:
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
        with logfire.span("context_assembly.get_project_context", project_id=project_id):
            try:
                # Get project and its context provider resources
                with logfire.span("context_assembly.db_queries"):
                    with self.db_session_factory() as db:
                        project_repo = ProjectRepository(db)
                        resource_repo = ContextProviderResourceRepository(db)

                        project = project_repo.get_by_id(project_id)
                        if not project:
                            raise ValueError(f"Project {project_id} not found")

                        linked_resources = resource_repo.get_resources_for_project(project_id)

                # Extract URIs from project description
                with logfire.span("context_assembly.extract_uris"):
                    detected_uris = self._extract_uris_from_text(project.specification.content)

                # Categorize resources by strategy
                on_demand_resources: list[OnDemandResourceInfo] = []
                eager_resource_tasks: list[Coroutine[None, None, EagerContextData]] = []
                resource_errors: list[ResourceRetrievalError] = []
                eager_context: list[EagerContextData] = []

                linked_uris = {resource.resource_uri for resource in linked_resources}

                all_resources: list[tuple[str, str | None]] = []
                # Add explicit links
                all_resources.extend(
                    [(resource.resource_uri, resource.description) for resource in linked_resources]
                )
                # Add detected URIs
                all_resources.extend(
                    [(uri, None) for uri in detected_uris if uri not in linked_uris]
                )

                logfire.info(
                    "Resources discovered",
                    linked_resources=len(linked_resources),
                    detected_uris=len(detected_uris),
                    total_resources=len(all_resources),
                )

                # Categorize resources by strategy
                with logfire.span("context_assembly.categorize_resources"):
                    for resource_uri, description in all_resources:
                        try:
                            resource_info = await self.get_resource_info(resource_uri, description)
                        except (NoProviderFound, ContextProviderUnavailable) as e:
                            resource_errors.append(
                                ResourceRetrievalError(
                                    resource_uri=resource_uri, error_message=str(e)
                                )
                            )
                            continue

                        if resource_info.retrieval_strategy == ContextStrategy.ON_DEMAND:
                            on_demand_resources.append(
                                OnDemandResourceInfo(
                                    uri=resource_info.uri,
                                    description=resource_info.description,
                                    provider_type=resource_info.provider.provider_type,
                                    has_user_description=description is not None,
                                )
                            )
                        else:
                            eager_resource_tasks.append(self._load_eager_context(resource_info))

                # Load EAGER context in parallel
                with logfire.span(
                    "context_assembly.load_eager_context",
                    eager_tasks=len(eager_resource_tasks),
                ):
                    eager_results = await asyncio.gather(
                        *eager_resource_tasks, return_exceptions=True
                    )

                    for result in eager_results:
                        if isinstance(result, BaseException):
                            logfire.error(
                                "Eager context loading failed",
                                error=str(result),
                                exc_info=result,
                            )
                        else:
                            eager_context.append(result)

                result = ProjectContextData(
                    eager_context=eager_context,
                    on_demand_resources=on_demand_resources,
                    provider_errors=resource_errors,
                )

                logfire.info(
                    "Context assembly complete",
                    eager_contexts=len(eager_context),
                    on_demand_resources=len(on_demand_resources),
                    errors=len(resource_errors),
                )

                return result

            except Exception as e:
                logfire.error(
                    "Context assembly failed",
                    project_id=project_id,
                    error=str(e),
                    exc_info=e,
                )
                raise

    async def _load_eager_context(self, resource: ResourceInfo) -> EagerContextData:
        """Load EAGER context for a single resource."""
        try:
            resource_data = await resource.provider.get_resource(resource.uri)
            return EagerContextData(
                uri=resource.uri,
                description=resource.description,
                provider_type=resource.provider.provider_type,
                data=resource_data,
            )
        except Exception:
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
        with logfire.span(
            "context_assembly.get_on_demand_context",
            resource_uri=resource_uri,
            query_length=len(query),
        ):
            try:
                provider, error = self._get_provider_instance(resource_uri)
                if not provider:
                    logfire.warn(
                        "No provider found for URI",
                        resource_uri=resource_uri,
                        error=error,
                    )
                    raise ValueError(error or f"No provider found for URI: {resource_uri}")

                logfire.info("Getting on-demand context", provider_type=provider.provider_type)
                result = await provider.get_relevant_context(resource_uri, query)
                logfire.info("On-demand context retrieved", result_length=len(result))
                return result

            except Exception as e:
                logfire.error(
                    "Failed to get on-demand context",
                    resource_uri=resource_uri,
                    error=str(e),
                    exc_info=e,
                )
                raise

    async def get_resource_info(self, resource_uri: str, description: str | None) -> ResourceInfo:
        # TODO: This can probably live somewhere else, and needs tests
        provider_class = self.context_provider_registry.get_provider_for_uri(resource_uri)
        if not provider_class:
            raise NoProviderFound(f"No context provider found for URI: {resource_uri}")

        # May raise ContextProviderUnavailable if provider cannot be instantiated
        provider = provider_class.create_instance()

        if not description:
            description = await provider.generate_resource_description(resource_uri)

        retrieval_strategy = provider.get_retrieval_strategy(resource_uri)
        return ResourceInfo(
            uri=resource_uri,
            description=description,
            provider=provider,
            retrieval_strategy=retrieval_strategy,
        )

    def list_available_providers(self) -> list[str]:
        """List all available context provider types."""
        return self.context_provider_registry.list_keys()


# Global context assembly service instance
context_assembly_service = ContextAssemblyService()
