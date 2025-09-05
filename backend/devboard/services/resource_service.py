"""Service layer for context provider resource operations."""

from sqlalchemy.orm import Session

from devboard.context_providers.registry import ContextProviderRegistry, context_provider_registry
from devboard.db.models import ContextProviderResource, Project, Task
from devboard.db.repositories import ContextProviderResourceRepository


class UnsupportedResourceUriError(Exception):
    """Raised when a resource URI is not supported by any registered context provider."""

    def __init__(self, resource_uri: str):
        super().__init__(f"No context provider found for resource URI: {resource_uri}")
        self.resource_uri = resource_uri


class ResourceService:
    """Service layer for context provider resource operations with M2M support."""

    def __init__(self, db: Session, context_provider_registry_instance: ContextProviderRegistry | None = None):
        self.db = db
        self.repository = ContextProviderResourceRepository(db)
        self.context_provider_registry = context_provider_registry_instance or context_provider_registry

    def determine_provider_name(self, resource_uri: str) -> str:
        """Determine the provider name for a given resource URI.

        Args:
            resource_uri: The resource URI to analyze

        Returns:
            Provider name for the resource

        Raises:
            UnsupportedResourceUriError: If no provider can handle this URI
        """
        provider_class = self.context_provider_registry.get_provider_for_uri(resource_uri)
        if not provider_class:
            raise UnsupportedResourceUriError(resource_uri)
        return provider_class.provider_type

    async def generate_description(self, resource_uri: str) -> str:
        """Generate a description for the resource if user didn't provide one.

        Args:
            resource_uri: The resource URI

        Returns:
            Final description to use

        Raises:
            UnsupportedResourceUriError: If no provider can handle this URI
        """
        provider_class = self.context_provider_registry.get_provider_for_uri(resource_uri)
        if not provider_class:
            raise UnsupportedResourceUriError(resource_uri)

        provider = provider_class.create_instance()
        description = await provider.generate_resource_description(resource_uri)
        return description

    async def find_or_create_resource(
        self, resource_uri: str, description: str | None = None
    ) -> ContextProviderResource:
        """Find existing resource by URI or create new one.

        Args:
            resource_uri: The resource URI
            description: Optional user-provided description

        Returns:
            Existing or newly created resource

        Raises:
            UnsupportedResourceUriError: If no provider can handle this URI
        """
        # Try to find existing resource
        existing = self.repository.get_by_uri(resource_uri)
        if existing:
            return existing

        # Create new resource
        provider_name = self.determine_provider_name(resource_uri)
        if not description:
            description = await self.generate_description(resource_uri)

        return self.repository.create_resource(
            resource_uri=resource_uri, provider_name=provider_name, description=description
        )

    async def create_project_resource(
        self, project_id: int, resource_uri: str, description: str | None = None
    ) -> ContextProviderResource:
        """Create or find resource and link to project.

        Args:
            project_id: The project ID
            resource_uri: The resource URI
            description: Optional user-provided description

        Returns:
            Resource linked to the project

        Raises:
            UnsupportedResourceUriError: If no provider can handle this URI
        """
        resource = await self.find_or_create_resource(resource_uri, description)
        self.repository.link_resource_to_project(resource.id, project_id)
        return resource

    async def create_task_resource(
        self, task_id: int, resource_uri: str, description: str | None = None
    ) -> ContextProviderResource:
        """Create or find resource and link to task.

        Args:
            task_id: The task ID
            resource_uri: The resource URI
            description: Optional user-provided description

        Returns:
            Resource linked to the task

        Raises:
            UnsupportedResourceUriError: If no provider can handle this URI
        """
        resource = await self.find_or_create_resource(resource_uri, description)
        self.repository.link_resource_to_task(resource.id, task_id)
        return resource

    def get_resources_for_project(self, project_id: int) -> list[ContextProviderResource]:
        """Get all context provider resources for a project.

        Args:
            project_id: The project ID

        Returns:
            List of context provider resources for the project
        """
        return self.repository.get_resources_for_project(project_id)

    def get_resources_for_task(self, task_id: int) -> list[ContextProviderResource]:
        """Get all context provider resources for a task.

        Args:
            task_id: The task ID

        Returns:
            List of context provider resources for the task
        """
        return self.repository.get_resources_for_task(task_id)

    def delete_project_resource(self, project_id: int, resource_id: int) -> bool:
        """Unlink resource from project with cascade deletion.

        Args:
            project_id: The project ID (for validation)
            resource_id: The resource ID to unlink

        Returns:
            True if resource was unlinked, False if not found or doesn't belong to project
        """
        return self.repository.delete_project_resource(project_id, resource_id)

    def delete_task_resource(self, task_id: int, resource_id: int) -> bool:
        """Unlink resource from task with cascade deletion.

        Args:
            task_id: The task ID (for validation)
            resource_id: The resource ID to unlink

        Returns:
            True if resource was unlinked, False if not found or doesn't belong to task
        """
        return self.repository.delete_task_resource(task_id, resource_id)

    # New methods enabled by M2M relationships

    def get_projects_for_resource(self, resource_id: int) -> list[Project]:
        """Get all projects that use a specific resource.

        Args:
            resource_id: The resource ID

        Returns:
            List of projects linked to the resource
        """
        return self.repository.get_projects_for_resource(resource_id)

    def get_tasks_for_resource(self, resource_id: int) -> list[Task]:
        """Get all tasks that use a specific resource.

        Args:
            resource_id: The resource ID

        Returns:
            List of tasks linked to the resource
        """
        return self.repository.get_tasks_for_resource(resource_id)

    def get_resource_usage_count(self, resource_id: int) -> int:
        """Get total usage count for a resource across all projects and tasks.

        Args:
            resource_id: The resource ID

        Returns:
            Total number of projects and tasks using this resource
        """
        projects = self.repository.get_projects_for_resource(resource_id)
        tasks = self.repository.get_tasks_for_resource(resource_id)
        return len(projects) + len(tasks)
