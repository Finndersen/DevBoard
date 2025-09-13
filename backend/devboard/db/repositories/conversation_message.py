"""Task conversation message repository for message data access operations."""

from typing import TypeVar

from sqlalchemy import delete, select

from devboard.db.models import ProjectConversationMessage, TaskConversationMessage
from devboard.db.models.messages import BaseConversationMessage, MessageType
from devboard.db.repositories.base import BaseRepository

MessageT = TypeVar("MessageT", bound=BaseConversationMessage)


class BaseConversationMessageRepository[MessageT](BaseRepository[BaseConversationMessage]):
    """
    Abstract base repository for Project and Task conversation messages
    """

    MESSAGE_MODEL: type[MessageT]

    def get_all_for_entity(self, entity_id: int, exclude_tool_calls: bool = False) -> list[MessageT]:
        """Get all messages for an entity (task or project)."""
        stmt = select(self.MESSAGE_MODEL).where(self.MESSAGE_MODEL.parent_id == entity_id)
        if exclude_tool_calls:
            stmt = stmt.where(self.MESSAGE_MODEL.message_type.not_in([MessageType.TOOL_CALL, MessageType.TOOL_RESULT]))
        stmt = stmt.order_by(self.MESSAGE_MODEL.timestamp.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, message_id: int) -> MessageT | None:
        """Get a message by its ID.

        Args:
            message_id: The message ID to search for

        Returns:
            TaskConversationMessage instance if found, None otherwise
        """
        stmt = select(self.MESSAGE_MODEL).where(self.MESSAGE_MODEL.id == message_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, message: MessageT) -> MessageT:
        """Create a new message.

        Args:
            message: TaskConversationMessage instance to create

        Returns:
            Created message with assigned ID
        """
        self.db.add(message)
        self.db.flush()  # Get the ID without committing
        return message

    def update(self, message: MessageT) -> MessageT:
        """Update an existing message.

        Args:
            message: TaskConversationMessage instance to update

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
        stmt = delete(self.MESSAGE_MODEL).where(self.MESSAGE_MODEL.id == message_id)
        result = self.db.execute(stmt)
        return result.rowcount > 0

    def delete_all_for_entity(self, entity_id: int) -> int:
        """Delete all messages for a task.

        Args:
            entity_id: The task ID to delete messages for

        Returns:
            Number of messages deleted
        """
        stmt = delete(self.MESSAGE_MODEL).where(self.MESSAGE_MODEL.parent_id == entity_id)
        result = self.db.execute(stmt)
        return result.rowcount


class TaskConversationMessageRepository(BaseConversationMessageRepository[TaskConversationMessage]):
    """Repository for task conversation message data access operations."""

    MESSAGE_MODEL = TaskConversationMessage


class ProjectConversationMessageRepository(BaseConversationMessageRepository[ProjectConversationMessage]):
    """Repository for project conversation message data access operations."""

    MESSAGE_MODEL = ProjectConversationMessage

    def get_by_project(self, project_id: int) -> list[ProjectConversationMessage]:
        """Get all messages for a project ordered by timestamp."""
        return self.get_all_for_entity(project_id)

    def delete_by_project(self, project_id: int) -> int:
        """Delete all messages for a project."""
        return self.delete_all_for_entity(project_id)
