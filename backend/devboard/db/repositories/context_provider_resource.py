"""Context provider resource repository for context resource data access operations."""

from sqlalchemy import select

from devboard.db.models import ContextProviderResource
from devboard.db.repositories.base import BaseRepository


class ContextProviderResourceRepository(BaseRepository[ContextProviderResource]):
    """Repository for context provider resource data access operations."""

    def get_by_parent(self, parent_id: int, parent_type: str) -> list[ContextProviderResource]:
        """Get all context provider resources for a parent entity.

        Args:
            parent_id: The parent entity ID
            parent_type: The parent entity type (e.g., 'project', 'task')

        Returns:
            List of context provider resources for the parent
        """
        stmt = select(ContextProviderResource).where(
            ContextProviderResource.parent_id == parent_id,
            ContextProviderResource.parent_type == parent_type,
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, resource_id: int) -> ContextProviderResource | None:
        """Get a context provider resource by its ID.

        Args:
            resource_id: The resource ID to search for

        Returns:
            ContextProviderResource instance if found, None otherwise
        """
        stmt = select(ContextProviderResource).where(ContextProviderResource.id == resource_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, resource: ContextProviderResource) -> ContextProviderResource:
        """Create a new context provider resource.

        Args:
            resource: ContextProviderResource instance to create

        Returns:
            Created resource with assigned ID
        """
        self.db.add(resource)
        self.db.flush()  # Get the ID without committing
        return resource

    def update(self, resource: ContextProviderResource) -> ContextProviderResource:
        """Update an existing context provider resource.

        Args:
            resource: ContextProviderResource instance to update

        Returns:
            Updated resource
        """
        self.db.merge(resource)
        return resource

    def delete_by_id(self, resource_id: int) -> bool:
        """Delete a context provider resource by its ID.

        Args:
            resource_id: The resource ID to delete

        Returns:
            True if resource was deleted, False if not found
        """
        resource = self.get_by_id(resource_id)
        if resource:
            self.db.delete(resource)
            return True
        return False

    def delete_by_parent(self, parent_id: int, parent_type: str) -> int:
        """Delete all context provider resources for a parent entity.

        Args:
            parent_id: The parent entity ID
            parent_type: The parent entity type

        Returns:
            Number of resources deleted
        """
        resources = self.get_by_parent(parent_id, parent_type)
        count = len(resources)
        for resource in resources:
            self.db.delete(resource)
        return count

    def get_resources_for_project(self, project_id: int) -> list[ContextProviderResource]:
        """Get all context provider resources for a specific project.

        Args:
            project_id: The project ID

        Returns:
            List of context provider resources for the project
        """
        return self.get_by_parent(project_id, "project")

    def get_resources_for_task(self, task_id: int) -> list[ContextProviderResource]:
        """Get all context provider resources for a specific task.

        Args:
            task_id: The task ID

        Returns:
            List of context provider resources for the task
        """
        return self.get_by_parent(task_id, "task")

    def create_project_resource(
        self, project_id: int, resource_uri: str, description: str | None = None
    ) -> ContextProviderResource:
        """Create a new context provider resource for a project.

        Args:
            project_id: The project ID
            resource_uri: The resource URI
            description: Optional user-provided description

        Returns:
            Created resource with assigned ID
        """
        resource = ContextProviderResource(
            parent_id=project_id,
            parent_type="project",
            resource_uri=resource_uri,
            description=description,
        )
        return self.create(resource)

    def create_task_resource(
        self, task_id: int, resource_uri: str, description: str | None = None
    ) -> ContextProviderResource:
        """Create a new context provider resource for a task.

        Args:
            task_id: The task ID
            resource_uri: The resource URI
            description: Optional user-provided description

        Returns:
            Created resource with assigned ID
        """
        resource = ContextProviderResource(
            parent_id=task_id,
            parent_type="task",
            resource_uri=resource_uri,
            description=description,
        )
        return self.create(resource)

    def delete_project_resource(self, project_id: int, resource_id: int) -> bool:
        """Delete a context provider resource from a project.

        Args:
            project_id: The project ID (for validation)
            resource_id: The resource ID to delete

        Returns:
            True if resource was deleted, False if not found or doesn't belong to project
        """
        resource = self.get_by_id(resource_id)
        if resource and resource.parent_id == project_id and resource.parent_type == "project":
            self.db.delete(resource)
            return True
        return False

    def delete_task_resource(self, task_id: int, resource_id: int) -> bool:
        """Delete a context provider resource from a task.

        Args:
            task_id: The task ID (for validation)
            resource_id: The resource ID to delete

        Returns:
            True if resource was deleted, False if not found or doesn't belong to task
        """
        resource = self.get_by_id(resource_id)
        if resource and resource.parent_id == task_id and resource.parent_type == "task":
            self.db.delete(resource)
            return True
        return False
