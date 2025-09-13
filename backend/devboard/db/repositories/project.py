"""Project repository for project data access operations."""

from sqlalchemy import select

from devboard.db.models import Project
from devboard.db.models.document import DocumentType
from devboard.db.repositories.base import BaseRepository
from devboard.db.repositories.document import DocumentRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for project data access operations with document management."""

    def __init__(self, db):
        super().__init__(db)
        self.document_repo = DocumentRepository(db)

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

    def create(self, name: str, description: str, **kwargs) -> Project:
        """Create a new project with required documents.

        Args:
            name: Project name
            description: Project description
            **kwargs: Additional project fields

        Returns:
            Created project with assigned ID and documents
        """
        # Create required specification document
        specification_doc = self.document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")

        # Create project with document reference
        project = Project(
            name=name,
            description=description,
            specification_document_id=specification_doc.id,
            **kwargs,
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
        return project

    def update_details_content(self, project: Project, content: str) -> Project:
        """Update project details content.

        Args:
            project: Project instance
            content: New details content

        Returns:
            Updated project
        """
        self.document_repo.update_content(project.specification, content)
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
