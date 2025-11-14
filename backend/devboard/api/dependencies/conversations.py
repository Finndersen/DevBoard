from fastapi import Depends, HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.roles.base import Role
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.factories import create_agent_conversation_service, create_agent_role_for_conversation
from devboard.api.dependencies.repositories import (
    get_conversation_repository,
    get_document_repository,
    get_project_repository,
    get_task_repository,
)
from devboard.api.dependencies.services import get_agent_config_service
from devboard.db.models import Conversation, ParentEntityType, Project, Task
from devboard.db.repositories import ConversationRepository, DocumentRepository, ProjectRepository, TaskRepository


def get_conversation_parent_entity(
    conversation: Conversation = Depends(get_verified_conversation),
    task_repo: TaskRepository = Depends(get_task_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
) -> Task | Project:
    """Get the parent entity (Task or Project) for a conversation.

    Args:
        conversation: Verified conversation instance
        task_repo: Task repository
        project_repo: Project repository

    Returns:
        Task or Project instance

    Raises:
        HTTPException: 404 if parent entity not found, 400 if unsupported entity type
    """
    if conversation.parent_entity_type == ParentEntityType.TASK:
        task = task_repo.get_by_id(conversation.parent_entity_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found for conversation")
        return task

    elif conversation.parent_entity_type == ParentEntityType.PROJECT:
        project = project_repo.get_by_id(conversation.parent_entity_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found for conversation")
        return project

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported parent entity type: {conversation.parent_entity_type}",
        )


def get_agent_role_for_conversation(
    conversation: Conversation = Depends(get_verified_conversation),
    parent_entity: Task | Project = Depends(get_conversation_parent_entity),
    document_repo: DocumentRepository = Depends(get_document_repository),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
) -> Role:
    """Get agent role for a conversation.

    FastAPI dependency that creates the appropriate role based on the conversation's
    configuration and parent entity.

    Args:
        conversation: Verified conversation instance
        parent_entity: Parent entity (Task or Project)
        document_repo: Document repository
        agent_config_service: Agent configuration service

    Returns:
        Role instance for the conversation

    Raises:
        HTTPException: 400 if unsupported agent role for entity type
    """
    return create_agent_role_for_conversation(conversation, parent_entity, document_repo, agent_config_service)


def get_agent_conversation_service(
    conversation: Conversation = Depends(get_verified_conversation),
    parent_entity: Task | Project = Depends(get_conversation_parent_entity),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    role: Role = Depends(get_agent_role_for_conversation),
) -> BaseAgentConversationService:
    """Get conversation service instance.

    FastAPI dependency that creates the appropriate conversation service (PydanticAI or Claude Code)
    based on the conversation's engine configuration.

    Args:
        conversation: Verified conversation instance
        parent_entity: Parent entity (Task or Project)
        conversation_repo: Conversation repository
        role: Role instance for the conversation

    Returns:
        BaseAgentConversationService instance (PydanticAI or Claude Code implementation)

    Raises:
        HTTPException: 400 if unsupported engine
    """
    return create_agent_conversation_service(conversation, role, parent_entity, conversation_repo)
