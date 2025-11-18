"""Service dependency injection functions."""

from fastapi import Depends

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.engines.agent_engines import agent_engine_registry
from devboard.agents.language_models import llm_registry
from devboard.api.dependencies.repositories import (
    get_configuration_repository,
    get_context_provider_resource_repository,
    get_conversation_repository,
    get_document_repository,
    get_project_repository,
    get_task_repository,
)
from devboard.context_providers.registry import context_provider_registry
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
from devboard.services.conversation_service import ConversationService
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


def get_conversation_service(
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationService:
    """Get ConversationService instance."""
    return ConversationService(
        conversation_repo=conversation_repo,
        agent_config_service=agent_config_service,
    )


def get_task_service(
    conversation_service: ConversationService = Depends(get_conversation_service),
    document_repo: DocumentRepository = Depends(get_document_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """Get TaskService instance."""
    return TaskService(
        conversation_service=conversation_service,
        document_repo=document_repo,
        task_repo=task_repo,
        conversation_repo=conversation_repo,
    )


def get_project_service(
    conversation_service: ConversationService = Depends(get_conversation_service),
    document_repo: DocumentRepository = Depends(get_document_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """Get ProjectService instance."""
    return ProjectService(
        conversation_service=conversation_service,
        document_repo=document_repo,
        project_repo=project_repo,
    )
