"""Context provider link repository for context link data access operations."""

from sqlalchemy import select

from devboard.db.models import ContextProviderLink
from devboard.repositories.base import BaseRepository


class ContextProviderLinkRepository(BaseRepository[ContextProviderLink]):
    """Repository for context provider link data access operations."""

    def get_by_parent(self, parent_id: int, parent_type: str) -> list[ContextProviderLink]:
        """Get all context provider links for a parent entity.

        Args:
            parent_id: The parent entity ID
            parent_type: The parent entity type (e.g., 'project', 'task')

        Returns:
            List of context provider links for the parent
        """
        stmt = select(ContextProviderLink).where(
            ContextProviderLink.parent_id == parent_id,
            ContextProviderLink.parent_type == parent_type,
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, link_id: int) -> ContextProviderLink | None:
        """Get a context provider link by its ID.

        Args:
            link_id: The link ID to search for

        Returns:
            ContextProviderLink instance if found, None otherwise
        """
        stmt = select(ContextProviderLink).where(ContextProviderLink.id == link_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, link: ContextProviderLink) -> ContextProviderLink:
        """Create a new context provider link.

        Args:
            link: ContextProviderLink instance to create

        Returns:
            Created link with assigned ID
        """
        self.db.add(link)
        self.db.flush()  # Get the ID without committing
        return link

    def update(self, link: ContextProviderLink) -> ContextProviderLink:
        """Update an existing context provider link.

        Args:
            link: ContextProviderLink instance to update

        Returns:
            Updated link
        """
        self.db.merge(link)
        return link

    def delete_by_id(self, link_id: int) -> bool:
        """Delete a context provider link by its ID.

        Args:
            link_id: The link ID to delete

        Returns:
            True if link was deleted, False if not found
        """
        link = self.get_by_id(link_id)
        if link:
            self.db.delete(link)
            return True
        return False

    def delete_by_parent(self, parent_id: int, parent_type: str) -> int:
        """Delete all context provider links for a parent entity.

        Args:
            parent_id: The parent entity ID
            parent_type: The parent entity type

        Returns:
            Number of links deleted
        """
        links = self.get_by_parent(parent_id, parent_type)
        count = len(links)
        for link in links:
            self.db.delete(link)
        return count
