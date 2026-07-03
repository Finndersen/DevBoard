from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import HTTPException
from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.conversation_history import create_conversation_history_service
from devboard.agents.engines import AgentEngine
from devboard.agents.engines.claude_code import ClaudeCodeAgentExecutionService
from devboard.agents.engines.codex import CodexAgentExecutionService
from devboard.agents.engines.internal import PydanticAIAgentExecutionService
from devboard.agents.execution.agent_execution import AgentExecutionService
from devboard.agents.roles import AgentRole, AgentRoleType
from devboard.agents.roles.background_agent import BackgroundAgentRole
from devboard.agents.roles.project_qa import ProjectQAAgentRole
from devboard.agents.roles.task_finalisation import TaskFinalisationAgentRole
from devboard.agents.roles.task_implementation import TaskImplementationAgentRole
from devboard.agents.roles.task_planning import TaskPlanningAgentRole
from devboard.agents.roles.task_pr_review import TaskPRReviewAgentRole
from devboard.db.models import Conversation, Project, Task
from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.repositories import (
    BackgroundAgentRepository,
    BackgroundAgentRunRepository,
    ConversationRepository,
    DocumentRepository,
    LogEntryRepository,
    TaskRepository,
)
from devboard.db.repositories.codebase import CodebaseRepository
from devboard.db.repositories.implementation_plan import TaskImplementationPlanRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.integrations.github import GitHubIntegration
from devboard.services.integration_service import IntegrationService
from devboard.services.log_entry_service import LogEntryService
from devboard.services.oauth_service import OAuthService
from devboard.services.task_implementation_plan import TaskImplementationPlanService
from devboard.services.task_service import TaskService


async def create_agent_role_for_conversation(
    conversation: Conversation,
    document_repo: DocumentRepository,
    agent_config_service: AgentConfigService,
    integration_service: IntegrationService,
    task_service: TaskService,
    conversation_repo: ConversationRepository,
    working_dir: str,
) -> AgentRole:
    """Create the appropriate role based on conversation type and parent entity.

    Non-dependency helper that can be called directly from any context.
    """
    parent_entity = conversation.get_parent_entity(load_task_context=True)
    parent_conversation_id = conversation.id
    plan_service = TaskImplementationPlanService(TaskImplementationPlanRepository(conversation_repo.db))
    if isinstance(parent_entity, Task):
        # Create role based on agent_role type for tasks
        if conversation.agent_role == AgentRoleType.TASK_PLANNING:
            return TaskPlanningAgentRole(
                task=parent_entity,
                document_repository=document_repo,
                agent_config_service=agent_config_service,
                task_service=task_service,
                conversation_repo=conversation_repo,
                conversation_id=parent_conversation_id,
                working_dir=working_dir,
                plan_service=plan_service,
            )
        elif conversation.agent_role == AgentRoleType.TASK_IMPLEMENTATION:
            # Create GitHub integration (no API calls - just object instantiation)
            github_integration = integration_service.get_integration_instance(GitHubIntegration)
            return TaskImplementationAgentRole(
                task=parent_entity,
                document_repository=document_repo,
                agent_config_service=agent_config_service,
                task_service=task_service,
                github_integration=github_integration,
                conversation_repo=conversation_repo,
                conversation_id=parent_conversation_id,
                plan_service=plan_service,
                working_dir=working_dir,
            )
        elif conversation.agent_role == AgentRoleType.TASK_PR_REVIEW:
            # Create GitHub integration (no API calls - just object instantiation)
            github_integration = integration_service.get_integration_instance(GitHubIntegration)
            try:
                return TaskPRReviewAgentRole(
                    task=parent_entity,
                    task_service=task_service,
                    github_integration=github_integration,
                    working_dir=working_dir,
                    conversation_repo=conversation_repo,
                    agent_config_service=agent_config_service,
                    conversation_id=parent_conversation_id,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
        elif conversation.agent_role == AgentRoleType.TASK_FINALISATION:
            return TaskFinalisationAgentRole(
                task=parent_entity,
                task_service=task_service,
                working_dir=working_dir,
                conversation_repo=conversation_repo,
                agent_config_service=agent_config_service,
                conversation_id=parent_conversation_id,
                document_repo=document_repo,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported agent role for task: {conversation.agent_role}",
            )
    elif isinstance(parent_entity, Project):
        # Must be a project
        if conversation.agent_role == AgentRoleType.PROJECT:
            return ProjectQAAgentRole(
                project=parent_entity,
                document_repository=document_repo,
                agent_config_service=agent_config_service,
                task_service=task_service,
                conversation_repo=conversation_repo,
                conversation_id=parent_conversation_id,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported agent role for project: {conversation.agent_role}",
            )
    elif isinstance(parent_entity, BackgroundAgent):
        if conversation.agent_role == AgentRoleType.BACKGROUND_AGENT:
            agent_config = agent_config_service.get_agent_configuration(conversation.agent_role)
            system_prompt = agent_config.custom_instructions or parent_entity.prompt
            log_entry_repo = LogEntryRepository(conversation_repo.db)
            task_repo = TaskRepository(conversation_repo.db)
            background_agent_repo = BackgroundAgentRepository(conversation_repo.db)
            agent_run_repo = BackgroundAgentRunRepository(conversation_repo.db)
            log_entry_service = LogEntryService(log_entry_repo, task_repo)
            return BackgroundAgentRole(
                system_prompt=system_prompt,
                task_service=task_service,
                conversation_repo=conversation_repo,
                document_repo=document_repo,
                agent_config_service=agent_config_service,
                integration_service=integration_service,
                project_repo=ProjectRepository(conversation_repo.db),
                codebase_repo=CodebaseRepository(conversation_repo.db),
                background_agent=parent_entity,
                conversation_id=parent_conversation_id,
                log_entry_service=log_entry_service,
                background_agent_repo=background_agent_repo,
                agent_run_repo=agent_run_repo,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported agent role for background agent: {conversation.agent_role}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported parent entity type: {type(parent_entity).__name__}",
        )


def create_agent_execution_service(
    conversation: Conversation,
    role: AgentRole,
    conversation_repo: ConversationRepository,
    agent_config_service: AgentConfigService,
    working_dir: str,
    additional_tools: list[Tool] | None = None,
    oauth_service: OAuthService | None = None,
    interrupt_event: asyncio.Event | None = None,
    additional_write_dirs: list[str] | None = None,
    effort: Literal["low", "medium", "high"] | None = None,
    log_entry_repo: LogEntryRepository | None = None,
) -> AgentExecutionService:
    """Create the appropriate execution service based on engine type.

    Non-dependency helper that can be called directly from any context.
    Internally creates the appropriate history service.

    Args:
        conversation: The conversation instance
        role: The role defining agent behavior
        conversation_repo: Repository for conversation operations
        agent_config_service: Service for loading agent configuration
        additional_tools: Optional extra tools beyond those defined by the role
        oauth_service: Optional OAuthService for OAuth-authenticated MCP servers
        interrupt_event: Optional asyncio.Event for graceful interrupt signaling
        effort: Optional effort level for Claude Code engine ("low", "medium", "high")
        log_entry_repo: Optional repository for querying log entries for event context injection

    Returns:
        AgentExecutionService instance (PydanticAI or ClaudeCode)

    Raises:
        HTTPException: If engine type is unsupported
    """
    history_service = create_conversation_history_service(conversation, conversation_repo)

    if conversation.engine == AgentEngine.INTERNAL:
        return PydanticAIAgentExecutionService(
            conversation=conversation,
            role=role,
            conversation_repository=conversation_repo,
            history_service=history_service,
            agent_config_service=agent_config_service,
            working_dir=working_dir,
            additional_tools=additional_tools,
            oauth_service=oauth_service,
            interrupt_event=interrupt_event,
            log_entry_repo=log_entry_repo,
        )
    elif conversation.engine == AgentEngine.CLAUDE_CODE:
        return ClaudeCodeAgentExecutionService(
            conversation=conversation,
            role=role,
            conversation_repository=conversation_repo,
            history_service=history_service,
            agent_config_service=agent_config_service,
            working_dir=working_dir,
            additional_tools=additional_tools,
            oauth_service=oauth_service,
            interrupt_event=interrupt_event,
            additional_write_dirs=additional_write_dirs,
            effort=effort,
            log_entry_repo=log_entry_repo,
        )
    elif conversation.engine == AgentEngine.CODEX:
        return CodexAgentExecutionService(
            conversation=conversation,
            role=role,
            conversation_repository=conversation_repo,
            history_service=history_service,
            agent_config_service=agent_config_service,
            working_dir=working_dir,
            additional_tools=additional_tools,
            oauth_service=oauth_service,
            interrupt_event=interrupt_event,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported engine: {conversation.engine}",
        )
