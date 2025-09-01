"""Project repository for project data access operations."""

from sqlalchemy import select

from devboard.db.models import Project
from devboard.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for project data access operations."""

    def get_by_id(self, project_id: int) -> Project | None:
        """Get a project by its ID.

        Args:
            project_id: The project ID to search for

        Returns:
            Project instance if found, None otherwise
        """
        stmt = select(Project).where(Project.id == project_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(self) -> list[Project]:
        """Get all projects.

        Returns:
            List of all projects
        """
        stmt = select(Project)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, project: Project) -> Project:
        """Create a new project.

        Args:
            project: Project instance to create

        Returns:
            Created project with assigned ID
        """
        self.db.add(project)
        self.db.flush()  # Get the ID without committing
        return project

    def update(self, project: Project) -> Project:
        """Update an existing project.

        Args:
            project: Project instance to update

        Returns:
            Updated project
        """
        self.db.merge(project)
        return project

    def delete_by_id(self, project_id: int) -> bool:
        """Delete a project by its ID.

        Args:
            project_id: The project ID to delete

        Returns:
            True if project was deleted, False if not found
        """
        project = self.get_by_id(project_id)
        if project:
            self.db.delete(project)
            return True
        return False
