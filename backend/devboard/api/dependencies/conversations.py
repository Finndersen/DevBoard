from fastapi import Depends, HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.roles import Role
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.factories import create_agent_conversation_service, create_agent_role_for_conversation
from devboard.api.dependencies.repositories import get_conversation_repository, get_document_repository
from devboard.api.dependencies.services import get_agent_config_service
from devboard.db.models import Codebase, Conversation, Project, Task
from devboard.db.models.conversation import InvalidParentEntityTypeError, ParentEntityNotFoundError
from devboard.db.repositories import ConversationRepository, DocumentRepository


def _get_parent_entity_or_raise(conversation: Conversation) -> Task | Project | Codebase:
    """Get parent entity for a conversation with HTTP exception handling.

    Helper function that wraps conversation.get_parent_entity() and converts
    exceptions to appropriate HTTP responses.

    Args:
        conversation: Conversation instance

    Returns:
        Task, Project, or Codebase instance

    Raises:
        HTTPException: 404 if entity not found, 400 if invalid entity type or session error
    """
    try:
        return conversation.get_parent_entity()
    except ParentEntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidParentEntityTypeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        # Session not attached
        raise HTTPException(status_code=400, detail=str(e)) from e


def get_agent_role_for_conversation(
    conversation: Conversation = Depends(get_verified_conversation),
    document_repo: DocumentRepository = Depends(get_document_repository),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
) -> Role:
    """Get agent role for a conversation.

    FastAPI dependency that creates the appropriate role based on the conversation's
    configuration and parent entity.

    Args:
        conversation: Verified conversation instance
        document_repo: Document repository
        agent_config_service: Agent configuration service

    Returns:
        Role instance for the conversation

    Raises:
        HTTPException: 400 if unsupported agent role for entity type, 404 if parent entity not found
    """
    parent_entity = _get_parent_entity_or_raise(conversation)
    return create_agent_role_for_conversation(conversation, parent_entity, document_repo, agent_config_service)


def get_agent_conversation_service(
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    role: Role = Depends(get_agent_role_for_conversation),
) -> BaseAgentConversationService:
    """Get conversation service instance.

    FastAPI dependency that creates the appropriate conversation service (PydanticAI or Claude Code)
    based on the conversation's engine configuration.

    Args:
        conversation: Verified conversation instance
        conversation_repo: Conversation repository
        role: Role instance for the conversation

    Returns:
        BaseAgentConversationService instance (PydanticAI or Claude Code implementation)

    Raises:
        HTTPException: 400 if unsupported engine, 404 if parent entity not found
    """
    parent_entity = _get_parent_entity_or_raise(conversation)
    return create_agent_conversation_service(conversation, role, parent_entity, conversation_repo)
