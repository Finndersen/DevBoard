"""Service dependency injection functions."""

import dataclasses

from fastapi import Depends

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.engines.agent_engines import agent_engine_registry
from devboard.agents.execution.background_agent_runner import BackgroundAgentRunner
from devboard.api.dependencies.repositories import (
    get_agent_role_config_repository,
    get_background_agent_run_repository,
    get_configuration_repository,
    get_conversation_repository,
    get_custom_field_repository,
    get_document_repository,
    get_language_model_repository,
    get_log_entry_repository,
    get_mcp_server_repository,
    get_oauth_repository,
    get_project_repository,
    get_task_implementation_plan_repository,
    get_task_repository,
    get_worktree_slot_repository,
)
from devboard.config.integration_configs import DevBoardConfig, WorktreeLocationMode
from devboard.db.repositories import (
    AgentRoleConfigRepository,
    ConfigurationRepository,
    ConversationRepository,
    CustomFieldRepository,
    DocumentRepository,
    LanguageModelRepository,
    LogEntryRepository,
    MCPServerRepository,
    OAuthRepository,
    ProjectRepository,
    TaskRepository,
    WorktreeSlotRepository,
)
from devboard.db.repositories.background_agent import BackgroundAgentRunRepository
from devboard.db.repositories.implementation_plan import TaskImplementationPlanRepository
from devboard.services.codebase_investigation import CodebaseInvestigationService
from devboard.services.config_service import ConfigService
from devboard.services.conversation_service import ConversationService
from devboard.services.global_context_service import GlobalContextService
from devboard.services.integration_service import IntegrationService
from devboard.services.language_model_service import LanguageModelService
from devboard.services.log_entry_service import LogEntryService
from devboard.services.mcp_service import MCPService
from devboard.services.oauth_service import OAuthService
from devboard.services.project_service import ProjectService
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_implementation_plan import TaskImplementationPlanService
from devboard.services.task_service import TaskService
from devboard.services.template_service import TemplateService
from devboard.services.workspace import WorkspaceService
from devboard.services.workspace.pool_manager import WorktreePoolManager


def get_global_context_service() -> GlobalContextService:
    """Get GlobalContextService instance."""
    return GlobalContextService()


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
    agent_role_config_repo: AgentRoleConfigRepository = Depends(get_agent_role_config_repository),
    config_service: ConfigService = Depends(get_config_service),
    language_model_repo: LanguageModelRepository = Depends(get_language_model_repository),
) -> AgentConfigService:
    """Get AgentConfigService instance."""
    return AgentConfigService(
        agent_role_config_repo=agent_role_config_repo,
        config_service=config_service,
        language_model_repo=language_model_repo,
        engine_registry=agent_engine_registry,
    )


def get_language_model_service(
    language_model_repo: LanguageModelRepository = Depends(get_language_model_repository),
) -> LanguageModelService:
    """Get LanguageModelService instance."""
    return LanguageModelService(language_model_repo)


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


def get_pool_manager(
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
    config_service: ConfigService = Depends(get_config_service),
) -> WorktreePoolManager:
    """Get WorktreePoolManager instance."""
    config = config_service.get_config(DevBoardConfig)
    worktree_location_mode = config.worktree_location_mode if config else WorktreeLocationMode.CENTRAL
    return WorktreePoolManager(worktree_slot_repo=worktree_slot_repo, worktree_location_mode=worktree_location_mode)


def get_workspace_service(
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    config_service: ConfigService = Depends(get_config_service),
) -> WorkspaceService:
    """Get WorkspaceService instance."""
    config = config_service.get_config(DevBoardConfig)
    worktree_location_mode = config.worktree_location_mode if config else WorktreeLocationMode.CENTRAL
    return WorkspaceService(
        worktree_slot_repo=worktree_slot_repo,
        conversation_repo=conversation_repo,
        worktree_location_mode=worktree_location_mode,
    )


def get_system_event_emitter(
    log_entry_repo: LogEntryRepository = Depends(get_log_entry_repository),
) -> SystemEventEmitter:
    """Get SystemEventEmitter instance."""
    return SystemEventEmitter(log_entry_repo=log_entry_repo)


def get_task_service(
    conversation_service: ConversationService = Depends(get_conversation_service),
    document_repo: DocumentRepository = Depends(get_document_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    custom_field_repo: CustomFieldRepository = Depends(get_custom_field_repository),
    system_event_emitter: SystemEventEmitter = Depends(get_system_event_emitter),
):
    """Get TaskService instance."""
    return TaskService(
        conversation_service=conversation_service,
        document_repo=document_repo,
        task_repo=task_repo,
        custom_field_repo=custom_field_repo,
        system_event_emitter=system_event_emitter,
    )


def get_task_implementation_plan_service(
    plan_repo: TaskImplementationPlanRepository = Depends(get_task_implementation_plan_repository),
) -> TaskImplementationPlanService:
    """Get TaskImplementationPlanService instance."""
    return TaskImplementationPlanService(plan_repo=plan_repo)


def get_project_service(
    conversation_service: ConversationService = Depends(get_conversation_service),
    document_repo: DocumentRepository = Depends(get_document_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
    system_event_emitter: SystemEventEmitter = Depends(get_system_event_emitter),
):
    """Get ProjectService instance."""
    return ProjectService(
        conversation_service=conversation_service,
        document_repo=document_repo,
        project_repo=project_repo,
        system_event_emitter=system_event_emitter,
    )


def get_log_entry_service(
    log_entry_repo: LogEntryRepository = Depends(get_log_entry_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
) -> LogEntryService:
    """Get LogEntryService instance."""
    return LogEntryService(log_entry_repo=log_entry_repo, task_repo=task_repo)


def get_oauth_service(
    oauth_repo: OAuthRepository = Depends(get_oauth_repository),
) -> OAuthService:
    """Get OAuthService instance."""
    return OAuthService(oauth_repo=oauth_repo)


def get_mcp_service(
    mcp_server_repo: MCPServerRepository = Depends(get_mcp_server_repository),
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> MCPService:
    """Get MCPService instance."""
    return MCPService(mcp_server_repository=mcp_server_repo, oauth_service=oauth_service)


def get_background_agent_runner(
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    agent_run_repo: BackgroundAgentRunRepository = Depends(get_background_agent_run_repository),
) -> BackgroundAgentRunner:
    """Get BackgroundAgentRunner instance."""
    return BackgroundAgentRunner(conversation_repo=conversation_repo, agent_run_repo=agent_run_repo)


@dataclasses.dataclass
class ExecutionServices:
    """Bundle of services needed for background agent execution and workflow actions."""

    conversation_repo: ConversationRepository
    document_repo: DocumentRepository
    task_repo: TaskRepository
    agent_config_service: AgentConfigService
    task_service: TaskService
    workspace_service: WorkspaceService
    integration_service: IntegrationService
    log_entry_repo: LogEntryRepository


def get_execution_services(
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
    task_service: TaskService = Depends(get_task_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    integration_service: IntegrationService = Depends(get_integration_service),
    log_entry_repo: LogEntryRepository = Depends(get_log_entry_repository),
) -> ExecutionServices:
    """Get all services needed for background agent execution.

    Intended for use with DependencyResolver (background tasks) or as a FastAPI
    dependency in endpoints that need the full execution service bundle.
    """
    return ExecutionServices(
        conversation_repo=conversation_repo,
        document_repo=document_repo,
        task_repo=task_repo,
        agent_config_service=agent_config_service,
        task_service=task_service,
        workspace_service=workspace_service,
        integration_service=integration_service,
        log_entry_repo=log_entry_repo,
    )
