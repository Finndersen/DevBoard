from fastapi import HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines import AgentEngine
from devboard.agents.engines.claude_code.agent_conversation import ClaudeCodeConversationService
from devboard.agents.engines.internal import PydanticAIConversationService
from devboard.agents.roles import AgentRoleType, Role
from devboard.agents.roles.project_qa import ProjectQARole
from devboard.agents.roles.task_implementation import TaskImplementationRole
from devboard.agents.roles.task_planning import TaskPlanningRole
from devboard.agents.roles.task_specification import TaskSpecificationRole
from devboard.db.models import Conversation, Task
from devboard.db.repositories import ConversationRepository, DocumentRepository


def create_agent_role_for_conversation(
    conversation: Conversation,
    document_repo: DocumentRepository,
    agent_config_service: AgentConfigService,
) -> Role:
    """Create the appropriate role based on conversation type and parent entity.

    Non-dependency helper that can be called directly from any context.

    Args:
        conversation: The conversation instance
        parent_entity: Either a Project or Task instance
        document_repo: Repository for document operations
        agent_config_service: Service for agent configuration

    Returns:
        Role instance configured for the conversation

    Raises:
        HTTPException: If agent role is unsupported for the entity type
    """
    parent_entity = conversation.get_parent_entity()
    if isinstance(parent_entity, Task):
        # Create role based on agent_role type for tasks
        if conversation.agent_role == AgentRoleType.TASK_SPECIFICATION:
            return TaskSpecificationRole(
                task=parent_entity,
                document_repository=document_repo,
                agent_config_service=agent_config_service,
            )
        elif conversation.agent_role == AgentRoleType.TASK_PLANNING:
            return TaskPlanningRole(
                task=parent_entity,
                document_repository=document_repo,
                agent_config_service=agent_config_service,
            )
        elif conversation.agent_role == AgentRoleType.TASK_IMPLEMENTATION:
            return TaskImplementationRole(task=parent_entity, document_repository=document_repo)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported agent role for task: {conversation.agent_role}",
            )
    else:
        # Must be a project
        if conversation.agent_role == AgentRoleType.PROJECT:
            return ProjectQARole(
                project=parent_entity,
                document_repository=document_repo,
                agent_config_service=agent_config_service,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported agent role for project: {conversation.agent_role}",
            )


def create_agent_conversation_service(
    conversation: Conversation,
    role: Role,
    conversation_repo: ConversationRepository,
) -> BaseAgentConversationService:
    """Create the appropriate service based on engine type.

    Non-dependency helper that can be called directly from any context.

    Args:
        conversation: The conversation instance
        role: The role defining agent behavior
        parent_entity: Either a Project or Task instance (for codebase path)
        conversation_repo: Repository for conversation operations

    Returns:
        BaseAgentConversationService instance (PydanticAI or ClaudeCode)

    Raises:
        HTTPException: If engine type is unsupported
    """
    # Create service based on engine type
    if conversation.engine == AgentEngine.INTERNAL:
        return PydanticAIConversationService(
            conversation=conversation,
            role=role,
            conversation_repository=conversation_repo,
        )
    elif conversation.engine == AgentEngine.CLAUDE_CODE:
        return ClaudeCodeConversationService(
            conversation=conversation,
            role=role,
            conversation_repository=conversation_repo,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported engine: {conversation.engine}",
        )
