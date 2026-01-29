from fastapi import Depends

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.roles import AgentRole
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.factories import create_agent_conversation_service, create_agent_role_for_conversation
from devboard.api.dependencies.repositories import get_conversation_repository, get_document_repository
from devboard.api.dependencies.services import (
    get_agent_config_service,
    get_integration_service,
    get_task_git_service,
    get_task_service,
)
from devboard.db.models import Conversation
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.integration_service import IntegrationService
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_service import TaskService


async def get_agent_role_for_conversation(
    conversation: Conversation = Depends(get_verified_conversation),
    document_repo: DocumentRepository = Depends(get_document_repository),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
    integration_service: IntegrationService = Depends(get_integration_service),
    task_service: TaskService = Depends(get_task_service),
    task_git_service: TaskGitService = Depends(get_task_git_service),
) -> AgentRole:
    """Get agent role for a conversation.

    FastAPI dependency that creates the appropriate role based on the conversation's
    configuration and parent entity.

    Args:
        conversation: Verified conversation instance
        document_repo: Document repository
        agent_config_service: Agent configuration service
        integration_service: Service for resolving integrations
        task_service: Service for task operations
        task_git_service: Service for task git operations

    Returns:
        Role instance for the conversation

    Raises:
        HTTPException: 400 if unsupported agent role for entity type, 404 if parent entity not found
    """
    return await create_agent_role_for_conversation(
        conversation,
        document_repo,
        agent_config_service,
        integration_service=integration_service,
        task_service=task_service,
        task_git_service=task_git_service,
    )


def get_agent_conversation_service(
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    role: AgentRole = Depends(get_agent_role_for_conversation),
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
    return create_agent_conversation_service(
        conversation=conversation,
        role=role,
        conversation_repo=conversation_repo,
    )
