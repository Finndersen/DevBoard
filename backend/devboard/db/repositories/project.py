"""Project repository for project data access operations."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from devboard.db.models import Document, Project
from devboard.db.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for project data access operations."""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def get_by_id(self, project_id: int) -> Project | None:
        """Get a project by its ID with parent relationship eager-loaded."""
        stmt = select(Project).where(Project.id == project_id).options(joinedload(Project.parent))
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_all(
        self,
        parent_project_id: int | None = None,
        root_only: bool = False,
        complete: bool | None = None,
    ) -> list[Project]:
        """Get projects with optional filtering.

        Args:
            parent_project_id: If provided, filter to initiatives under this parent.
            root_only: If True, return only root projects (no parent).
            complete: Filter by completion status. Defaults to False (non-complete only).
        """
        stmt = select(Project).options(joinedload(Project.parent))
        if parent_project_id is not None:
            stmt = stmt.where(Project.parent_project_id == parent_project_id)
        elif root_only:
            stmt = stmt.where(Project.parent_project_id == None)  # noqa: E711
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
        parent_project_id: int | None = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name
            description: Project description (optional)
            specification: Specification document instance
            custom_fields: Optional custom field values
            parent_project_id: Optional parent project ID (makes this an initiative)

        Returns:
            Created project with assigned ID
        """
        project = Project(
            name=name,
            description=description,
            specification_document_id=specification.id,
            custom_fields=custom_fields,
            parent_project_id=parent_project_id,
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
