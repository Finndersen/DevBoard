"""Service dependency injection functions."""

from fastapi import Depends, HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines.agent_engines import AgentEngine, agent_engine_registry
from devboard.agents.engines.claude_code import ClaudeCodeConversationService
from devboard.agents.engines.internal import PydanticAIConversationService
from devboard.agents.language_models import llm_registry
from devboard.agents.roles.base import Role
from devboard.agents.roles.project_qa import ProjectQARole
from devboard.agents.roles.task_implementation import TaskImplementationRole
from devboard.agents.roles.task_planning import TaskPlanningRole
from devboard.agents.roles.task_specification import TaskSpecificationRole
from devboard.agents.roles.types import AgentRoleType
from devboard.api.dependencies.entities import get_verified_conversation
from devboard.api.dependencies.repositories import (
    get_configuration_repository,
    get_context_provider_resource_repository,
    get_conversation_repository,
    get_document_repository,
    get_project_repository,
    get_task_repository,
)
from devboard.context_providers.registry import context_provider_registry
from devboard.db.models import Conversation, ParentEntityType, Project, Task
from devboard.db.repositories import (
    ConfigurationRepository,
    ContextProviderResourceRepository,
    ConversationRepository,
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.services.codebase_investigation import CodebaseInvestigationService
from devboard.services.config_service import ConfigService
from devboard.services.context_assembly import ContextAssemblyService
from devboard.services.integration_service import IntegrationService
from devboard.services.project_service import ProjectService
from devboard.services.prompt_action_service import PromptActionService
from devboard.services.resource_service import ResourceService
from devboard.services.task_service import TaskService
from devboard.services.template_service import TemplateService


def get_context_assembly_service(
    project_repo: ProjectRepository = Depends(get_project_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    resource_repo: ContextProviderResourceRepository = Depends(get_context_provider_resource_repository),
) -> ContextAssemblyService:
    """Get ContextAssemblyService instance."""
    return ContextAssemblyService(project_repo, task_repo, resource_repo)


def get_resource_service(
    resource_repo: ContextProviderResourceRepository = Depends(get_context_provider_resource_repository),
) -> ResourceService:
    """Get ResourceService instance."""
    return ResourceService(resource_repo, context_provider_registry)


def get_config_service(
    config_repo: ConfigurationRepository = Depends(get_configuration_repository),
) -> ConfigService:
    """Get ConfigService instance."""
    return ConfigService(config_repo)


def get_integration_service(
    config_repo: ConfigurationRepository = Depends(get_configuration_repository),
) -> IntegrationService:
    """Get IntegrationService instance."""
    return IntegrationService(config_repo)


def get_agent_config_service(
    config_service: ConfigService = Depends(get_config_service),
) -> AgentConfigService:
    """Get AgentConfigService instance."""
    return AgentConfigService(
        config_service=config_service,
        llm_registry=llm_registry,
        engine_registry=agent_engine_registry,
    )


def get_template_service() -> TemplateService:
    """Get TemplateService instance."""
    return TemplateService()


def get_codebase_investigation_service(
    template_service: TemplateService = Depends(get_template_service),
) -> CodebaseInvestigationService:
    """Get CodebaseInvestigationService instance."""
    return CodebaseInvestigationService(template_service)


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
) -> Role:
    """Get agent role for a conversation.

    This dependency creates the appropriate role based on the conversation's
    configuration and parent entity.

    Args:
        conversation: Verified conversation instance
        parent_entity: Parent entity (Task or Project)
        document_repo: Document repository

    Returns:
        Role instance for the conversation

    Raises:
        HTTPException: 400 if unsupported agent role for entity type
    """
    if isinstance(parent_entity, Task):
        # Create role based on agent_role type for tasks
        if conversation.agent_role == AgentRoleType.TASK_SPECIFICATION:
            return TaskSpecificationRole(task=parent_entity, document_repository=document_repo)
        elif conversation.agent_role == AgentRoleType.TASK_PLANNING:
            return TaskPlanningRole(task=parent_entity, document_repository=document_repo)
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
            return ProjectQARole(project=parent_entity, document_repository=document_repo)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported agent role for project: {conversation.agent_role}",
            )


def get_agent_conversation_service(
    conversation: Conversation = Depends(get_verified_conversation),
    parent_entity: Task | Project = Depends(get_conversation_parent_entity),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    role: Role = Depends(get_agent_role_for_conversation),
) -> BaseAgentConversationService:
    """Get conversation service instance.

    This dependency creates the appropriate conversation service (PydanticAI or Claude Code)
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
    # Get codebase path if parent is a task
    if isinstance(parent_entity, Task):
        codebase_path = parent_entity.codebase.local_path if parent_entity.codebase else None
    else:
        codebase_path = None

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
            codebase_path=codebase_path,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported engine: {conversation.engine}",
        )


def get_task_service(
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
):
    """Get TaskService instance."""
    return TaskService(
        conversation_repo=conversation_repo,
        document_repo=document_repo,
        task_repo=task_repo,
        agent_config_service=agent_config_service,
    )


def get_project_service(
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """Get ProjectService instance."""
    return ProjectService(
        conversation_repo=conversation_repo,
        document_repo=document_repo,
        project_repo=project_repo,
        agent_config_service=agent_config_service,
    )


def get_prompt_action_service(
    conversation_service: BaseAgentConversationService = Depends(get_agent_conversation_service),
) -> PromptActionService:
    """Get PromptActionService instance."""
    return PromptActionService(conversation_service=conversation_service)
