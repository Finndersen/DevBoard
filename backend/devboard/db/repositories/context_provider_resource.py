"""Context provider resource repository for context resource data access operations."""

from sqlalchemy import select

from devboard.db.models import ContextProviderResource, Project, Task
from devboard.db.models.base import (
    project_context_resource_association,
    task_context_resource_association,
)
from devboard.db.repositories.base import BaseRepository


class ContextProviderResourceRepository(BaseRepository[ContextProviderResource]):
    """Repository for context provider resource data access operations with M2M relationships."""

    def get_by_uri(self, resource_uri: str) -> ContextProviderResource | None:
        """Find a context provider resource by its URI.

        Args:
            resource_uri: The resource URI to search for

        Returns:
            ContextProviderResource instance if found, None otherwise
        """
        stmt = select(ContextProviderResource).where(
            ContextProviderResource.resource_uri == resource_uri
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id(self, resource_id: int) -> ContextProviderResource | None:
        """Get a context provider resource by its ID.

        Args:
            resource_id: The resource ID to search for

        Returns:
            ContextProviderResource instance if found, None otherwise
        """
        stmt = select(ContextProviderResource).where(ContextProviderResource.id == resource_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_resource(
        self, resource_uri: str, provider_name: str, description: str
    ) -> ContextProviderResource:
        """Create a new context provider resource.

        Args:
            resource_uri: The resource URI
            provider_name: The name of the context provider that can handle this resource
            description: Resource description

        Returns:
            Created resource with assigned ID
        """
        resource = ContextProviderResource(
            resource_uri=resource_uri,
            provider_name=provider_name,
            description=description,
        )
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

    def delete_resource(self, resource_id: int) -> bool:
        """Delete a context provider resource completely.

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

    def get_resources_for_project(self, project_id: int) -> list[ContextProviderResource]:
        """Get all context provider resources linked to a project.

        Args:
            project_id: The project ID

        Returns:
            List of context provider resources for the project
        """
        stmt = (
            select(ContextProviderResource)
            .join(project_context_resource_association)
            .where(project_context_resource_association.c.project_id == project_id)
            .order_by(project_context_resource_association.c.added_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_resources_for_task(self, task_id: int) -> list[ContextProviderResource]:
        """Get all context provider resources linked to a task.

        Args:
            task_id: The task ID

        Returns:
            List of context provider resources for the task
        """
        stmt = (
            select(ContextProviderResource)
            .join(task_context_resource_association)
            .where(task_context_resource_association.c.task_id == task_id)
            .order_by(task_context_resource_association.c.added_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def link_resource_to_project(self, resource_id: int, project_id: int) -> None:
        """Create M2M link between a resource and project.

        Args:
            resource_id: The resource ID
            project_id: The project ID
        """
        from sqlalchemy.dialects.sqlite import insert

        stmt = insert(project_context_resource_association).values(
            resource_id=resource_id, project_id=project_id
        )
        stmt = stmt.on_conflict_do_nothing()
        self.db.execute(stmt)

    def link_resource_to_task(self, resource_id: int, task_id: int) -> None:
        """Create M2M link between a resource and task.

        Args:
            resource_id: The resource ID
            task_id: The task ID
        """
        from sqlalchemy.dialects.sqlite import insert

        stmt = insert(task_context_resource_association).values(
            resource_id=resource_id, task_id=task_id
        )
        stmt = stmt.on_conflict_do_nothing()
        self.db.execute(stmt)

    def unlink_resource_from_project(self, resource_id: int, project_id: int) -> bool:
        """Remove M2M link between a resource and project.

        Args:
            resource_id: The resource ID
            project_id: The project ID

        Returns:
            True if link was removed, False if link didn't exist
        """
        stmt = project_context_resource_association.delete().where(
            project_context_resource_association.c.resource_id == resource_id,
            project_context_resource_association.c.project_id == project_id,
        )
        result = self.db.execute(stmt)
        return result.rowcount > 0

    def unlink_resource_from_task(self, resource_id: int, task_id: int) -> bool:
        """Remove M2M link between a resource and task.

        Args:
            resource_id: The resource ID
            task_id: The task ID

        Returns:
            True if link was removed, False if link didn't exist
        """
        stmt = task_context_resource_association.delete().where(
            task_context_resource_association.c.resource_id == resource_id,
            task_context_resource_association.c.task_id == task_id,
        )
        result = self.db.execute(stmt)
        return result.rowcount > 0

    def is_resource_orphaned(self, resource_id: int) -> bool:
        """Check if a resource has no remaining project or task links.

        Args:
            resource_id: The resource ID to check

        Returns:
            True if resource has no links, False if it has at least one link
        """
        # Check project links
        project_stmt = select(project_context_resource_association).where(
            project_context_resource_association.c.resource_id == resource_id
        )
        project_links = self.db.execute(project_stmt).first()

        if project_links:
            return False

        # Check task links
        task_stmt = select(task_context_resource_association).where(
            task_context_resource_association.c.resource_id == resource_id
        )
        task_links = self.db.execute(task_stmt).first()

        return task_links is None

    def get_projects_for_resource(self, resource_id: int) -> list[Project]:
        """Get all projects linked to a resource.

        Args:
            resource_id: The resource ID

        Returns:
            List of projects linked to the resource
        """
        stmt = (
            select(Project)
            .join(project_context_resource_association)
            .where(project_context_resource_association.c.resource_id == resource_id)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_tasks_for_resource(self, resource_id: int) -> list[Task]:
        """Get all tasks linked to a resource.

        Args:
            resource_id: The resource ID

        Returns:
            List of tasks linked to the resource
        """
        stmt = (
            select(Task)
            .join(task_context_resource_association)
            .where(task_context_resource_association.c.resource_id == resource_id)
        )
        return list(self.db.execute(stmt).scalars().all())

    # Higher-level methods that provide additional functionality beyond basic M2M operations

    def create_project_resource(
        self,
        project_id: int,
        resource_uri: str,
        provider_name: str,
        description: str,
    ) -> ContextProviderResource:
        """Create or find a resource and link it to a project.

        If a resource with the same URI already exists, it will be reused.
        Otherwise, a new resource will be created.
        """
        # Find existing resource or create new one
        resource = self.get_by_uri(resource_uri)
        if not resource:
            resource = self.create_resource(resource_uri, provider_name, description)

        # Link to project
        self.link_resource_to_project(resource.id, project_id)
        return resource

    def create_task_resource(
        self,
        task_id: int,
        resource_uri: str,
        provider_name: str,
        description: str,
    ) -> ContextProviderResource:
        """Create or find a resource and link it to a task.

        If a resource with the same URI already exists, it will be reused.
        Otherwise, a new resource will be created.
        """
        # Find existing resource or create new one
        resource = self.get_by_uri(resource_uri)
        if not resource:
            resource = self.create_resource(resource_uri, provider_name, description)

        # Link to task
        self.link_resource_to_task(resource.id, task_id)
        return resource

    def delete_project_resource(self, project_id: int, resource_id: int) -> bool:
        """Unlink resource from project with cascade deletion.

        If the resource becomes orphaned (not linked to any project or task),
        it will be completely removed from the database.
        """
        # Unlink from project
        unlinked = self.unlink_resource_from_project(resource_id, project_id)
        if not unlinked:
            return False

        # Check if resource is now orphaned and delete if so
        if self.is_resource_orphaned(resource_id):
            self.delete_resource(resource_id)

        return True

    def delete_task_resource(self, task_id: int, resource_id: int) -> bool:
        """Unlink resource from task with cascade deletion.

        If the resource becomes orphaned (not linked to any project or task),
        it will be completely removed from the database.
        """
        # Unlink from task
        unlinked = self.unlink_resource_from_task(resource_id, task_id)
        if not unlinked:
            return False

        # Check if resource is now orphaned and delete if so
        if self.is_resource_orphaned(resource_id):
            self.delete_resource(resource_id)

        return True
