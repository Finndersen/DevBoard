"""Project conversation message repository for message data access operations."""

from sqlalchemy import select

from devboard.db.models import ProjectConversationMessage
from devboard.db.repositories.base import BaseRepository


class ProjectConversationMessageRepository(BaseRepository[ProjectConversationMessage]):
    """Repository for project conversation message data access operations."""

    def get_by_id(self, message_id: int) -> ProjectConversationMessage | None:
        """Get a message by its ID.

        Args:
            message_id: The message ID to search for

        Returns:
            ProjectConversationMessage instance if found, None otherwise
        """
        stmt = select(ProjectConversationMessage).where(ProjectConversationMessage.id == message_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_project(self, project_id: int) -> list[ProjectConversationMessage]:
        """Get all messages for a specific project.

        Args:
            project_id: The project ID to get messages for

        Returns:
            List of messages for the project ordered by timestamp
        """
        stmt = (
            select(ProjectConversationMessage)
            .where(ProjectConversationMessage.project_id == project_id)
            .order_by(ProjectConversationMessage.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_recent_by_project(
        self, project_id: int, limit: int = 50
    ) -> list[ProjectConversationMessage]:
        """Get recent messages for a specific project.

        Args:
            project_id: The project ID to get messages for
            limit: Maximum number of messages to return

        Returns:
            List of recent messages for the project
        """
        stmt = (
            select(ProjectConversationMessage)
            .where(ProjectConversationMessage.project_id == project_id)
            .order_by(ProjectConversationMessage.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, message: ProjectConversationMessage) -> ProjectConversationMessage:
        """Create a new message.

        Args:
            message: ProjectConversationMessage instance to create

        Returns:
            Created message with assigned ID
        """
        self.db.add(message)
        self.db.flush()  # Get the ID without committing
        return message

    def update(self, message: ProjectConversationMessage) -> ProjectConversationMessage:
        """Update an existing message.

        Args:
            message: ProjectConversationMessage instance to update

        Returns:
            Updated message
        """
        self.db.merge(message)
        return message

    def delete_by_id(self, message_id: int) -> bool:
        """Delete a message by its ID.

        Args:
            message_id: The message ID to delete

        Returns:
            True if message was deleted, False if not found
        """
        message = self.get_by_id(message_id)
        if message:
            self.db.delete(message)
            return True
        return False

    def delete_by_project(self, project_id: int) -> int:
        """Delete all messages for a project.

        Args:
            project_id: The project ID to delete messages for

        Returns:
            Number of messages deleted
        """
        messages = self.get_by_project(project_id)
        count = len(messages)
        for message in messages:
            self.db.delete(message)
        return count
