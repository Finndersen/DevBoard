"""Service dependency injection functions."""

from fastapi import Depends, HTTPException

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines.agent_engines import AgentEngine, default_agent_engine_repository
from devboard.agents.engines.internal import ProjectAgent, PydanticAIConversationService
from devboard.agents.language_models import default_llm_repository
from devboard.agents.roles.types import AgentRole
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
from devboard.db.models import Conversation, ParentEntityType
from devboard.db.repositories import (
    ConfigurationRepository,
    ContextProviderResourceRepository,
    ConversationRepository,
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.services.agent_conversation_factory import create_task_conversation_service
from devboard.services.codebase_investigation import CodebaseInvestigationService
from devboard.services.config_service import ConfigService
from devboard.services.context_assembly import ContextAssemblyService
from devboard.services.integration_service import IntegrationService
from devboard.services.project_service import ProjectService
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
        llm_repository=default_llm_repository,
        engine_repository=default_agent_engine_repository,
    )


def get_template_service() -> TemplateService:
    """Get TemplateService instance."""
    return TemplateService()


def get_codebase_investigation_service(
    template_service: TemplateService = Depends(get_template_service),
) -> CodebaseInvestigationService:
    """Get CodebaseInvestigationService instance."""
    return CodebaseInvestigationService(template_service)


def get_agent_conversation_service(
    conversation: Conversation = Depends(get_verified_conversation),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
    context_service: ContextAssemblyService = Depends(get_context_assembly_service),
) -> BaseAgentConversationService:
    """Get conversation service instance using factory pattern based on conversation entity.

    This dependency creates the appropriate conversation service (PydanticAI or Claude Code)
    based on the conversation's configuration and parent entity.

    Args:
        conversation: Verified conversation instance
        conversation_repo: Conversation repository
        document_repo: Document repository
        task_repo: Task repository
        project_repo: Project repository
        context_service: Context assembly service

    Returns:
        BaseAgentConversationService instance (PydanticAI or Claude Code implementation)

    Raises:
        HTTPException: 404 if parent entity not found, 400 if unsupported entity type
    """
    # Load parent entity based on conversation type
    if conversation.parent_entity_type == ParentEntityType.TASK:
        task = task_repo.get_by_id(conversation.parent_entity_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found for conversation")

        # Use task factory
        return create_task_conversation_service(
            conversation=conversation,
            task=task,
            conversation_repo=conversation_repo,
            document_repo=document_repo,
            context_service=context_service,
        )

    elif conversation.parent_entity_type == ParentEntityType.PROJECT:
        project = project_repo.get_by_id(conversation.parent_entity_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found for conversation")

        # For projects, we only support INTERNAL engine with PROJECT role currently
        if conversation.engine != AgentEngine.INTERNAL or conversation.agent_role != AgentRole.PROJECT:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported configuration for project conversations: "
                f"engine={conversation.engine}, role={conversation.agent_role}",
            )

        agent = ProjectAgent(
            project=project,
            document_repository=document_repo,
            context_service=context_service,
            model_name=conversation.model_id,
        )

        return PydanticAIConversationService(
            conversation=conversation,
            agent=agent,
            conversation_repository=conversation_repo,
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported parent entity type: {conversation.parent_entity_type}",
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
