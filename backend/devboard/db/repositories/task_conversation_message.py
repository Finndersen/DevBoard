"""Task conversation message repository for message data access operations."""

from sqlalchemy import select

from devboard.db.models import TaskConversationMessage
from devboard.db.repositories.base import BaseRepository


class TaskConversationMessageRepository(BaseRepository[TaskConversationMessage]):
    """Repository for task conversation message data access operations."""

    def get_by_id(self, message_id: int) -> TaskConversationMessage | None:
        """Get a message by its ID.

        Args:
            message_id: The message ID to search for

        Returns:
            TaskConversationMessage instance if found, None otherwise
        """
        stmt = select(TaskConversationMessage).where(TaskConversationMessage.id == message_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_task(self, task_id: int) -> list[TaskConversationMessage]:
        """Get all messages for a specific task.

        Args:
            task_id: The task ID to get messages for

        Returns:
            List of messages for the task ordered by timestamp
        """
        stmt = (
            select(TaskConversationMessage)
            .where(TaskConversationMessage.task_id == task_id)
            .order_by(TaskConversationMessage.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_recent_by_task(
        self, task_id: int, limit: int = 50
    ) -> list[TaskConversationMessage]:
        """Get recent messages for a specific task.

        Args:
            task_id: The task ID to get messages for
            limit: Maximum number of messages to return

        Returns:
            List of recent messages for the task
        """
        stmt = (
            select(TaskConversationMessage)
            .where(TaskConversationMessage.task_id == task_id)
            .order_by(TaskConversationMessage.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, message: TaskConversationMessage) -> TaskConversationMessage:
        """Create a new message.

        Args:
            message: TaskConversationMessage instance to create

        Returns:
            Created message with assigned ID
        """
        self.db.add(message)
        self.db.flush()  # Get the ID without committing
        return message

    def update(self, message: TaskConversationMessage) -> TaskConversationMessage:
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
        message = self.get_by_id(message_id)
        if message:
            self.db.delete(message)
            return True
        return False

    def delete_by_task(self, task_id: int) -> int:
        """Delete all messages for a task.

        Args:
            task_id: The task ID to delete messages for

        Returns:
            Number of messages deleted
        """
        messages = self.get_by_task(task_id)
        count = len(messages)
        for message in messages:
            self.db.delete(message)
        return count
