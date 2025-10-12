"""Project repository for project data access operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from devboard.db.models import Document, Project
from devboard.db.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for project data access operations."""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

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

    def create(self, name: str, description: str | None, specification: "Document") -> Project:
        """Create a new project.

        Args:
            name: Project name
            description: Project description (optional)
            specification: Specification document instance

        Returns:
            Created project with assigned ID
        """
        project = Project(
            name=name,
            description=description,
            specification_document_id=specification.id,
        )

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
        self.db.flush()
        self.db.refresh(project)
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
            # Document will be cascade deleted via foreign key constraint
            self.db.delete(project)
            return True
        return False
