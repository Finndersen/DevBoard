"""Service for managing conversation lifecycle and transitions."""

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.types import AgentRoleType
from devboard.db.models import Conversation, ParentEntityType
from devboard.db.repositories import ConversationRepository


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
            model_id=agent_config.config.model_id,
            external_session_id=None,
        )
