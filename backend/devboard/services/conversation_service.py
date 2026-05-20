"""Service for managing conversation lifecycle and transitions."""

import dataclasses

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles import AgentRoleType
from devboard.db.models import Codebase, Conversation, ParentEntityType, Project, Task
from devboard.db.repositories import ConversationRepository

MAX_PROJECT_CONVERSATIONS = 20


@dataclasses.dataclass
class CreateConversationResult:
    """Result of creating a project conversation."""

    conversation: Conversation
    at_cap: bool


class ConversationService:
    """Service for managing conversation lifecycle and transitions.

    Handles complex operations like replacing conversations during phase transitions,
    reusing conversations when appropriate, and ensuring atomicity of conversation
    management operations.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
    ):
        """Initialize the conversation service.

        Args:
            conversation_repo: Repository for conversation data operations
            agent_config_service: Service for agent configuration
        """
        self.conversation_repo = conversation_repo
        self.agent_config_service = agent_config_service

    def create_initial_conversation_for_parent_entity(
        self,
        parent_entity_type: ParentEntityType,
        parent_entity_id: int,
        agent_role: AgentRoleType,
        model_id_override: str | None = None,
    ) -> Conversation:
        """Create initial active conversation for a parent entity.

        Gets the effective agent configuration for the specified role and creates
        an active conversation linked to the parent entity.

        Args:
            parent_entity_type: Type of the parent entity (TASK or PROJECT)
            parent_entity_id: ID of the parent entity
            agent_role: Agent role type for the conversation
            model_id_override: Optional model ID to use instead of the role's effective config model

        Returns:
            Created Conversation instance
        """
        config = self.agent_config_service.get_effective_config(agent_role)
        model_id = model_id_override if model_id_override is not None else (config.model.id if config.model else None)

        return self.conversation_repo.create(
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            agent_role=agent_role,
            engine=config.engine,
            model_id=model_id,
            external_session_id=None,
            is_active=True,
        )

    def replace_active_conversation(
        self,
        entity_type: ParentEntityType,
        entity_id: int,
        new_agent_role: AgentRoleType,
    ) -> Conversation:
        """Replace the active conversation with a new one.

        This is an atomic operation that:
        1. Archives the current active conversation (if exists)
        2. Creates a new conversation with the specified role

        Args:
            entity_type: Type of parent entity (PROJECT, TASK, CODEBASE)
            entity_id: ID of parent entity
            new_agent_role: Agent role for the new conversation

        Returns:
            Newly created Conversation instance
        """
        current_conversation = self.conversation_repo.get_active_conversation_for_entity(entity_type, entity_id)

        # Archive current conversation
        self.conversation_repo.archive_conversation(current_conversation.id)

        # Get configuration for new role
        agent_config = self.agent_config_service.get_agent_configuration(new_agent_role)

        # Create new conversation
        return self.conversation_repo.create(
            parent_entity_type=entity_type,
            parent_entity_id=entity_id,
            agent_role=new_agent_role,
            engine=agent_config.config.engine,
            model_id=agent_config.config.model.id if agent_config.config.model else None,
            external_session_id=None,
        )

    def reset_conversation(self, conversation: Conversation) -> Conversation:
        """Reset a conversation by deleting it and creating a new one with fresh config.

        This operation:
        1. Extracts parent entity info from the existing conversation
        2. Deletes the conversation (messages cascade delete)
        3. Creates a new conversation with the same agent role, re-evaluating agent config

        Args:
            conversation: The conversation to reset

        Returns:
            The newly created Conversation instance
        """
        # Extract parent entity info before deletion
        parent_entity_type = conversation.parent_entity_type
        parent_entity_id = conversation.parent_entity_id
        agent_role = conversation.agent_role

        # Delete the existing conversation (messages deleted via repository method)
        self.conversation_repo.delete_by_id(conversation.id)

        # Create new conversation with fresh config
        return self.create_initial_conversation_for_parent_entity(
            parent_entity_type=parent_entity_type,
            parent_entity_id=parent_entity_id,
            agent_role=agent_role,
        )

    def delete_conversations_for_parent(self, parent: Task | Project | Codebase) -> int:
        """Delete all conversations for a parent entity.

        Args:
            parent: The parent entity (Task, Project, or Codebase)

        Returns:
            Number of conversations deleted
        """
        if isinstance(parent, Task):
            parent_type = ParentEntityType.TASK
        elif isinstance(parent, Project):
            parent_type = ParentEntityType.PROJECT
        else:
            parent_type = ParentEntityType.CODEBASE

        return self.conversation_repo.delete_by_parent(parent_type, parent.id)

    def create_project_conversation(self, project_id: int) -> CreateConversationResult:
        """Create a new conversation for a project, enforcing the cap.

        If the cap (20) is reached, deletes the oldest conversation before creating.
        """
        count = self.conversation_repo.count_active_for_entity(ParentEntityType.PROJECT, project_id)

        if count >= MAX_PROJECT_CONVERSATIONS:
            oldest = self.conversation_repo.get_oldest_active_for_entity(ParentEntityType.PROJECT, project_id)
            if oldest:
                self.conversation_repo.delete_by_id(oldest.id)
                count -= 1

        conversation = self.create_initial_conversation_for_parent_entity(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=project_id,
            agent_role=AgentRoleType.PROJECT,
        )

        return CreateConversationResult(
            conversation=conversation,
            at_cap=(count + 1) >= MAX_PROJECT_CONVERSATIONS,
        )

    def set_conversation_title_from_message(self, conversation: Conversation, message: str) -> None:
        """Auto-set conversation title from first user message if not already set."""
        if conversation.title is None:
            title = message[:80].strip()
            if title:
                self.conversation_repo.update_title(conversation, title)
