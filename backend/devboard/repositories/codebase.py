"""Codebase repository for codebase data access operations."""

from sqlalchemy import select

from devboard.db.models import Codebase
from devboard.repositories.base import BaseRepository


class CodebaseRepository(BaseRepository[Codebase]):
    """Repository for codebase data access operations."""

    def get_by_id(self, codebase_id: int) -> Codebase | None:
        """Get a codebase by its ID.

        Args:
            codebase_id: The codebase ID to search for

        Returns:
            Codebase instance if found, None otherwise
        """
        stmt = select(Codebase).where(Codebase.id == codebase_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(self) -> list[Codebase]:
        """Get all codebases.

        Returns:
            List of all codebases
        """
        stmt = select(Codebase)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, codebase: Codebase) -> Codebase:
        """Create a new codebase.

        Args:
            codebase: Codebase instance to create

        Returns:
            Created codebase with assigned ID
        """
        self.db.add(codebase)
        self.db.flush()  # Get the ID without committing
        return codebase

    def update(self, codebase: Codebase) -> Codebase:
        """Update an existing codebase.

        Args:
            codebase: Codebase instance to update

        Returns:
            Updated codebase
        """
        self.db.merge(codebase)
        return codebase

    def delete_by_id(self, codebase_id: int) -> bool:
        """Delete a codebase by its ID.

        Args:
            codebase_id: The codebase ID to delete

        Returns:
            True if codebase was deleted, False if not found
        """
        codebase = self.get_by_id(codebase_id)
        if codebase:
            self.db.delete(codebase)
            return True
        return False
