"""Project repository for project data access operations."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from devboard.db.models import Document, Project
from devboard.db.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for project data access operations."""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def get_by_id(self, project_id: int) -> Project | None:
        """Get a project by its ID."""
        stmt = select(Project).where(Project.id == project_id)
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_all(
        self,
        complete: bool | None = None,
    ) -> list[Project]:
        """Get projects with optional filtering.

        Args:
            complete: Filter by completion status. Defaults to False (non-complete only).
        """
        stmt = select(Project)
        # Default: exclude complete projects
        filter_complete = complete if complete is not None else False
        stmt = stmt.where(Project.complete == filter_complete)
        return list(self.db.execute(stmt).unique().scalars().all())

    def create(
        self,
        name: str,
        description: str | None,
        specification: "Document",
        custom_fields: dict[str, Any] | None = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name
            description: Project description (optional)
            specification: Specification document instance
            custom_fields: Optional custom field values

        Returns:
            Created project with assigned ID
        """
        project = Project(
            name=name,
            description=description,
            specification_document_id=specification.id,
            custom_fields=custom_fields,
        )

        self.db.add(project)
        self.db.flush()  # Get the ID without committing
        return project

    def update(self, project: Project) -> Project:
        """Update an existing project."""
        self.db.merge(project)
        self.db.flush()
        self.db.refresh(project)
        return project

    def delete_by_id(self, project_id: int) -> bool:
        """Delete a project by its ID.

        Returns:
            True if project was deleted, False if not found
        """
        project = self.get_by_id(project_id)
        if project:
            # Document will be cascade deleted via foreign key constraint
            self.db.delete(project)
            return True
        return False
