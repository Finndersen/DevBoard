"""Repository for conversation and message data access operations."""

import datetime
from typing import TypedDict

from pydantic_ai.messages import ModelMessage
from sqlalchemy import delete, select
from sqlalchemy.orm import aliased

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.db.models import Conversation, ConversationMessage, MessageType, ParentEntityType
from devboard.db.repositories.base import BaseRepository


class SessionTaskInfo(TypedDict):
    external_session_id: str
    task_id: int
    task_title: str
    agent_role: str


class SessionSubAgentInfo(TypedDict):
    external_session_id: str
    agent_role: str
    parent_task_id: int | None
    parent_task_title: str | None


class ConversationListRow(TypedDict):
    conversation: Conversation
    parent_entity_name: str
    project_name: str | None


class NoActiveConversationError(Exception):
    """Raised when no active conversation exists for an entity."""

    pass


class ConversationRepository(BaseRepository[Conversation]):
    """Repository handling both conversations and messages."""

    # Conversation methods
    def get_by_id(self, conversation_id: int) -> Conversation | None:
        """Get conversation by ID."""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_conversation_for_entity(
        self,
        entity_type: ParentEntityType,
        entity_id: int,
    ) -> Conversation:
        """Get the currently active conversation for an entity.

        For task lifecycle management - returns the active conversation for the
        current phase.

        Args:
            entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
            entity_id: ID of parent entity

        Returns:
            Active Conversation

        Raises:
            NoActiveConversationError: If no active conversation exists for the entity
        """
        stmt = (
            select(Conversation)
            .where(
                Conversation.parent_entity_type == entity_type,
                Conversation.parent_entity_id == entity_id,
                Conversation.is_active == True,  # noqa: E712
                Conversation.parent_conversation_id.is_(None),  # Only top-level conversations
            )
            .order_by(Conversation.created_at.desc())
        )
        conversation = self.db.execute(stmt).scalar_one_or_none()
        if not conversation:
            raise NoActiveConversationError(f"No active conversation found for {entity_type.value} with id {entity_id}")
        return conversation

    def create(
        self,
        parent_entity_type: ParentEntityType,
        parent_entity_id: int,
        agent_role: AgentRoleType,
        engine: AgentEngine,
        model_id: str | None,
        external_session_id: str | None = None,
        is_active: bool = True,
        parent_conversation_id: int | None = None,
    ) -> Conversation:
        """Create a conversation with all parameters specified (low-level method).

        This is the primary low-level method for creating conversations. Higher-level
        services (like TaskService, ProjectService) should use this instead of
        constructing Conversation objects directly.

        Args:
            parent_entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
            parent_entity_id: ID of parent entity
            agent_role: Agent role for this conversation
            engine: Agent engine powering this conversation
            model_id: Model identifier (e.g., "anthropic:claude-sonnet-4") or None for default
            external_session_id: Optional external session ID for Claude Code/Gemini
            is_active: Whether this is the active conversation (default True)
            parent_conversation_id: Optional ID of parent conversation for sub-conversations

        Returns:
            New Conversation instance
        """
        conversation = Conversation(
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            agent_role=agent_role,
            engine=engine,
            model_id=model_id,
            external_session_id=external_session_id,
            is_active=is_active,
            parent_conversation_id=parent_conversation_id,
            last_activity_at=datetime.datetime.now(datetime.UTC),
        )

        self.db.add(conversation)
        self.db.flush()

        return conversation

    def update_last_activity(self, conversation: Conversation) -> None:
        conversation.last_activity_at = datetime.datetime.now(datetime.UTC)
        self.db.flush()

    def update_model(self, conversation: Conversation, model_id: str | None) -> Conversation:
        """Update the model for a conversation.

        Model can be changed within the same engine (e.g., Opus → Sonnet in Claude Code).

        Args:
            conversation: Conversation instance to update
            model_id: New model identifier or None for default

        Returns:
            Updated Conversation instance
        """
        conversation.model_id = model_id
        self.db.flush()

        return conversation

    def archive_conversation(self, conversation_id: int) -> None:
        """Archive a conversation by setting is_active=False.

        Called during task phase transitions to archive the previous phase's conversation.

        Args:
            conversation_id: ID of conversation to archive
        """
        conversation = self.get_by_id(conversation_id)
        if conversation:
            conversation.is_active = False
            conversation.archived_at = datetime.datetime.now(datetime.UTC)
            self.db.flush()

    def get_task_info_by_session_ids(self, session_ids: set[str]) -> dict[str, SessionTaskInfo]:
        """Get task association info for a set of session IDs.

        Returns a dict keyed by external_session_id for efficient O(1) lookup.
        Only returns entries for sessions linked to Task conversations (not Project/Codebase).
        """
        from devboard.db.models.task import Task

        stmt = (
            select(
                Conversation.external_session_id,
                Conversation.agent_role,
                Task.id,
                Task.title,
            )
            .join(Task, Task.id == Conversation.parent_entity_id)
            .where(
                Conversation.external_session_id.in_(session_ids),
                Conversation.parent_entity_type == ParentEntityType.TASK,
                Conversation.parent_conversation_id.is_(None),
            )
        )
        rows = self.db.execute(stmt).all()
        return {
            row.external_session_id: SessionTaskInfo(
                external_session_id=row.external_session_id,
                task_id=row.id,
                task_title=row.title,
                agent_role=row.agent_role.value if hasattr(row.agent_role, "value") else row.agent_role,
            )
            for row in rows
        }

    def get_sub_agent_info_by_session_ids(self, session_ids: set[str]) -> dict[str, SessionSubAgentInfo]:
        """Get sub-agent info for a set of session IDs.

        Returns a dict keyed by external_session_id for sessions that are sub-agent conversations
        (i.e. have a parent_conversation_id set).
        """
        from devboard.db.models.task import Task

        stmt = (
            select(
                Conversation.external_session_id,
                Conversation.agent_role,
                Task.id,
                Task.title,
            )
            .outerjoin(
                Task,
                (Task.id == Conversation.parent_entity_id) & (Conversation.parent_entity_type == ParentEntityType.TASK),
            )
            .where(
                Conversation.external_session_id.in_(session_ids),
                Conversation.parent_conversation_id.is_not(None),
            )
        )
        rows = self.db.execute(stmt).all()
        return {
            row.external_session_id: SessionSubAgentInfo(
                external_session_id=row.external_session_id,
                agent_role=row.agent_role.value if hasattr(row.agent_role, "value") else row.agent_role,
                parent_task_id=row.id,
                parent_task_title=row.title,
            )
            for row in rows
        }

    def update_external_session_id(self, conversation: Conversation, session_id: str | None) -> None:
        """Update the external session ID for a conversation.

        Used by Claude Code and other external engines to persist session continuity.

        Args:
            conversation: Conversation instance to update
            session_id: New session ID from external engine or None to clear
        """
        conversation.external_session_id = session_id
        self.db.flush()

    def get_all_top_level(self) -> list[ConversationListRow]:
        """Get all top-level, non-archived conversations ordered by last activity.

        Excludes sub-conversations, archived conversations, and conversations
        belonging to completed tasks. Includes enriched parent entity names
        via left outer joins to avoid N+1 queries.
        """
        from devboard.db.models.codebase import Codebase
        from devboard.db.models.project import Project
        from devboard.db.models.task import Task, TaskStatus

        TaskAlias = aliased(Task)
        ProjectAlias = aliased(Project)
        TaskProjectAlias = aliased(Project)
        CodebaseAlias = aliased(Codebase)

        stmt = (
            select(
                Conversation,
                TaskAlias.title.label("task_title"),
                ProjectAlias.name.label("project_name"),
                CodebaseAlias.name.label("codebase_name"),
                TaskAlias.status.label("task_status"),
                TaskProjectAlias.name.label("task_project_name"),
            )
            .outerjoin(
                TaskAlias,
                (Conversation.parent_entity_type == ParentEntityType.TASK)
                & (Conversation.parent_entity_id == TaskAlias.id),
            )
            .outerjoin(
                ProjectAlias,
                (Conversation.parent_entity_type == ParentEntityType.PROJECT)
                & (Conversation.parent_entity_id == ProjectAlias.id),
            )
            .outerjoin(
                CodebaseAlias,
                (Conversation.parent_entity_type == ParentEntityType.CODEBASE)
                & (Conversation.parent_entity_id == CodebaseAlias.id),
            )
            .outerjoin(
                TaskProjectAlias,
                TaskAlias.project_id == TaskProjectAlias.id,
            )
            .where(
                Conversation.parent_conversation_id.is_(None),
                Conversation.archived_at.is_(None),
            )
            # Exclude conversations for completed tasks
            .where(
                ~(
                    (Conversation.parent_entity_type == ParentEntityType.TASK)
                    & (TaskAlias.status == TaskStatus.COMPLETE)
                )
            )
            .order_by(Conversation.last_activity_at.desc().nullslast())
        )

        rows = self.db.execute(stmt).all()
        result: list[ConversationListRow] = []
        for row in rows:
            conversation = row[0]
            entity_type = conversation.parent_entity_type
            project_name: str | None = None
            if entity_type == ParentEntityType.TASK:
                name = row.task_title or ""
                project_name = row.task_project_name
            elif entity_type == ParentEntityType.PROJECT:
                name = row.project_name or ""
            else:
                name = row.codebase_name or ""
            result.append(
                ConversationListRow(conversation=conversation, parent_entity_name=name, project_name=project_name)
            )
        return result

    # Message methods (for internal agent messages)
    def get_messages(
        self,
        conversation_id: int,
        exclude_tool_calls: bool = False,
    ) -> list[ConversationMessage]:
        """Get all messages for a conversation."""
        stmt = select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
        if exclude_tool_calls:
            stmt = stmt.where(ConversationMessage.message_type.not_in([MessageType.TOOL_CALL, MessageType.TOOL_RESULT]))
        stmt = stmt.order_by(ConversationMessage.timestamp.asc())
        return list(self.db.execute(stmt).scalars().all())

    def create_message(
        self,
        conversation_id: int,
        message: ModelMessage,
    ) -> ConversationMessage:
        """Create a new message in a conversation."""
        db_message = ConversationMessage.from_pydantic_message(conversation_id, message)
        self.db.add(db_message)
        self.db.flush()

        # Update last_activity_at on the conversation
        conversation = self.db.get(Conversation, conversation_id)
        if conversation:
            conversation.last_activity_at = datetime.datetime.now(datetime.UTC)
            self.db.flush()

        return db_message

    def delete_messages(self, conversation_id: int) -> int:
        """Delete all messages in a conversation."""
        stmt = delete(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
        result = self.db.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined]

    def delete_tool_approval_messages(self, conversation_id: int) -> int:
        """
        Delete all messages associated with an incomplete tool approval cycle
        (including previous user message).
        """
        # Find the last user prompt message ID
        last_user_message_subq = (
            select(ConversationMessage.id)
            .where(
                ConversationMessage.message_type == MessageType.USER_PROMPT,
                ConversationMessage.conversation_id == conversation_id,
            )
            .order_by(ConversationMessage.id.desc())
            .limit(1)
            .scalar_subquery()
        )

        # Delete all messages from that point onwards
        stmt = delete(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.id >= last_user_message_subq,
        )

        return self.db.execute(stmt).rowcount  # type: ignore[attr-defined]

    def delete_by_id(self, conversation_id: int) -> bool:
        """Delete a conversation, its sub-conversations, and all messages by ID.

        Deletes sub-conversations first to avoid FK constraint violations when
        deleting the parent (e.g., called by ConversationService.reset_conversation()).

        Args:
            conversation_id: ID of the conversation to delete

        Returns:
            True if conversation was deleted, False if not found
        """
        # Find and delete all sub-conversations first (FK constraint)
        sub_conv_stmt = select(Conversation.id).where(Conversation.parent_conversation_id == conversation_id)
        sub_conv_ids = list(self.db.execute(sub_conv_stmt).scalars().all())

        if sub_conv_ids:
            # Delete sub-conversation messages
            msg_stmt = delete(ConversationMessage).where(ConversationMessage.conversation_id.in_(sub_conv_ids))
            self.db.execute(msg_stmt)
            # Delete sub-conversations
            del_stmt = delete(Conversation).where(Conversation.id.in_(sub_conv_ids))
            self.db.execute(del_stmt)

        # Delete messages first (SQL delete bypasses cascade)
        self.delete_messages(conversation_id)

        # Delete the conversation record
        stmt = delete(Conversation).where(Conversation.id == conversation_id)
        result = self.db.execute(stmt)

        return result.rowcount > 0  # type: ignore[attr-defined]

    def delete_by_parent(self, parent_entity_type: ParentEntityType, parent_entity_id: int) -> int:
        """Hard-delete all conversations and their messages for a parent entity.

        Used during parent entity deletion to ensure no orphaned conversation records.
        Messages are explicitly deleted first because we use SQL delete() which bypasses
        ORM cascade rules. Using ORM delete would be slower for bulk operations.

        Args:
            parent_entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
            parent_entity_id: ID of parent entity

        Returns:
            Number of conversations deleted
        """
        # Get all conversation IDs for the parent
        stmt = select(Conversation.id).where(
            Conversation.parent_entity_type == parent_entity_type,
            Conversation.parent_entity_id == parent_entity_id,
        )
        conversation_ids = list(self.db.execute(stmt).scalars().all())

        if not conversation_ids:
            return 0

        # Delete all messages for these conversations first
        msg_stmt = delete(ConversationMessage).where(ConversationMessage.conversation_id.in_(conversation_ids))
        self.db.execute(msg_stmt)

        # Delete the conversations
        conv_stmt = delete(Conversation).where(Conversation.id.in_(conversation_ids))
        result = self.db.execute(conv_stmt)

        return result.rowcount  # type: ignore[attr-defined]
