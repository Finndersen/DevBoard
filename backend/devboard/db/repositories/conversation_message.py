"""Task conversation message repository for message data access operations."""

from typing import TypeVar, cast

from sqlalchemy import delete, select

from devboard.db.models import ProjectConversationMessage, TaskConversationMessage
from devboard.db.models.messages import BaseConversationMessage, MessageType
from devboard.db.repositories.base import BaseRepository

MessageT = TypeVar("MessageT", bound=BaseConversationMessage)


class BaseConversationMessageRepository[MessageT: BaseConversationMessage](BaseRepository[MessageT]):
    """
    Abstract base repository for Project and Task conversation messages
    """

    MESSAGE_MODEL: type[MessageT]

    def get_all_for_entity(self, entity_id: int, exclude_tool_calls: bool = False) -> list[MessageT]:
        """Get all messages for an entity (task or project)."""
        model = cast(type[BaseConversationMessage], self.MESSAGE_MODEL)
        stmt = select(model).where(model.parent_id == entity_id)  # type: ignore[arg-type]
        if exclude_tool_calls:
            stmt = stmt.where(model.message_type.not_in([MessageType.TOOL_CALL, MessageType.TOOL_RESULT]))
        stmt = stmt.order_by(model.timestamp.asc())
        return list(self.db.execute(stmt).scalars().all())  # type: ignore[return-value,arg-type]

    def get_by_id(self, message_id: int) -> MessageT | None:
        """Get a message by its ID.

        Args:
            message_id: The message ID to search for

        Returns:
            TaskConversationMessage instance if found, None otherwise
        """
        model = cast(type[BaseConversationMessage], self.MESSAGE_MODEL)
        stmt = select(model).where(model.id == message_id)
        return self.db.execute(stmt).scalar_one_or_none()  # type: ignore[return-value]

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
        model = cast(type[BaseConversationMessage], self.MESSAGE_MODEL)
        stmt = delete(model).where(model.id == message_id)
        result = self.db.execute(stmt)
        return result.rowcount > 0

    def delete_all_for_entity(self, entity_id: int) -> int:
        """Delete all messages for a task.

        Args:
            entity_id: The task ID to delete messages for

        Returns:
            Number of messages deleted
        """
        model = cast(type[BaseConversationMessage], self.MESSAGE_MODEL)
        stmt = delete(model).where(model.parent_id == entity_id)  # type: ignore[arg-type]
        result = self.db.execute(stmt)
        return result.rowcount

    def delete_tool_approval_messages(self, entity_id: int) -> int:
        """
        Delete all messages associated with an incomplete tool approval cycle (including previous user message).

        :param entity_id:
        :return:
        """
        model = cast(type[BaseConversationMessage], self.MESSAGE_MODEL)
        stmt = delete(model).where(
            model.id
            >= (
                select(model.id)
                .where(
                    model.message_type == MessageType.USER_PROMPT,  # type: ignore[arg-type]
                    model.parent_id == entity_id,  # type: ignore[arg-type]
                )
                .order_by(model.id.desc())
                .limit(1)
                .scalar_subquery()
            )
        )

        return self.db.execute(stmt).rowcount


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
