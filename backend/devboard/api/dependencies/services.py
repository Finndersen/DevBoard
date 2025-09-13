"""Service dependency injection functions."""

from fastapi import Depends

from devboard.agents.llm_service import LLMService
from devboard.api.dependencies.repositories import (
    get_configuration_repository,
    get_context_provider_resource_repository,
    get_project_repository,
    get_task_repository,
)
from devboard.context_providers.registry import context_provider_registry
from devboard.db.repositories import (
    ConfigurationRepository,
    ContextProviderResourceRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.services.codebase_investigation import CodebaseInvestigationService
from devboard.services.config_service import ConfigService
from devboard.services.context_assembly import ContextAssemblyService
from devboard.services.integration_service import IntegrationService
from devboard.services.resource_service import ResourceService
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


def get_llm_service(
    config_service: ConfigService = Depends(get_config_service),
) -> LLMService:
    """Get LLMService instance."""
    return LLMService(config_service)


def get_template_service() -> TemplateService:
    """Get TemplateService instance."""
    return TemplateService()


def get_codebase_investigation_service(
    template_service: TemplateService = Depends(get_template_service),
) -> CodebaseInvestigationService:
    """Get CodebaseInvestigationService instance."""
    return CodebaseInvestigationService(template_service)
