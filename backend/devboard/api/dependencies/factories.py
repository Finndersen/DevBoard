from __future__ import annotations

from fastapi import HTTPException
from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.agent_execution import AgentExecutionService
from devboard.agents.conversation_history import ConversationHistoryService
from devboard.agents.engines import AgentEngine
from devboard.agents.engines.claude_code import ClaudeCodeAgentExecutionService, ClaudeCodeConversationHistoryService
from devboard.agents.engines.internal import PydanticAIAgentExecutionService, PydanticAIConversationHistoryService
from devboard.agents.roles import AgentRole, AgentRoleType
from devboard.agents.roles.project_qa import ProjectQAAgentRole
from devboard.agents.roles.task_implementation import TaskImplementationAgentRole
from devboard.agents.roles.task_planning import TaskPlanningAgentRole
from devboard.agents.roles.task_pr_review import TaskPRReviewAgentRole
from devboard.db.models import Conversation, Project, Task
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.integrations.github import GitHubIntegration
from devboard.services.integration_service import IntegrationService
from devboard.services.oauth_service import OAuthService
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_service import TaskService


async def create_agent_role_for_conversation(
    conversation: Conversation,
    document_repo: DocumentRepository,
    agent_config_service: AgentConfigService,
    integration_service: IntegrationService,
    task_service: TaskService,
    task_git_service: TaskGitService,
) -> AgentRole:
    """Create the appropriate role based on conversation type and parent entity.

    Non-dependency helper that can be called directly from any context.
    """
    parent_entity = conversation.get_parent_entity()
    if isinstance(parent_entity, Task):
        # Create role based on agent_role type for tasks
        if conversation.agent_role == AgentRoleType.TASK_PLANNING:
            return TaskPlanningAgentRole(
                task=parent_entity,
                document_repository=document_repo,
                agent_config_service=agent_config_service,
                task_service=task_service,
            )
        elif conversation.agent_role == AgentRoleType.TASK_IMPLEMENTATION:
            # Create GitHub integration (no API calls - just object instantiation)
            github_integration = integration_service.get_integration_instance(GitHubIntegration)
            return TaskImplementationAgentRole(
                task=parent_entity,
                document_repository=document_repo,
                agent_config_service=agent_config_service,
                task_service=task_service,
                task_git_service=task_git_service,
                github_integration=github_integration,
            )
        elif conversation.agent_role == AgentRoleType.TASK_PR_REVIEW:
            # Create GitHub integration (no API calls - just object instantiation)
            github_integration = integration_service.get_integration_instance(GitHubIntegration)
            try:
                return TaskPRReviewAgentRole(
                    task=parent_entity,
                    task_service=task_service,
                    github_integration=github_integration,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
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
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported agent role for project: {conversation.agent_role}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported parent entity type: {type(parent_entity).__name__}",
        )


def create_conversation_history_service(
    conversation: Conversation,
    conversation_repo: ConversationRepository,
) -> ConversationHistoryService:
    """Create the appropriate history service based on engine type.

    Non-dependency helper that can be called directly from any context.

    Args:
        conversation: The conversation instance
        conversation_repo: Repository for conversation operations

    Returns:
        ConversationHistoryService instance (PydanticAI or ClaudeCode)

    Raises:
        HTTPException: If engine type is unsupported
    """
    if conversation.engine == AgentEngine.INTERNAL:
        return PydanticAIConversationHistoryService(
            conversation=conversation,
            conversation_repository=conversation_repo,
        )
    elif conversation.engine == AgentEngine.CLAUDE_CODE:
        return ClaudeCodeConversationHistoryService(
            conversation=conversation,
            conversation_repository=conversation_repo,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported engine: {conversation.engine}",
        )


def create_agent_execution_service(
    conversation: Conversation,
    role: AgentRole,
    conversation_repo: ConversationRepository,
    agent_config_service: AgentConfigService,
    additional_tools: list[Tool] | None = None,
    oauth_service: OAuthService | None = None,
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

    Returns:
        AgentExecutionService instance (PydanticAI or ClaudeCode)

    Raises:
        HTTPException: If engine type is unsupported
    """
    # Create history service first
    history_service = create_conversation_history_service(conversation, conversation_repo)

    # Create execution service based on engine type
    if conversation.engine == AgentEngine.INTERNAL:
        return PydanticAIAgentExecutionService(
            conversation=conversation,
            role=role,
            conversation_repository=conversation_repo,
            history_service=history_service,
            agent_config_service=agent_config_service,
            additional_tools=additional_tools,
            oauth_service=oauth_service,
        )
    elif conversation.engine == AgentEngine.CLAUDE_CODE:
        return ClaudeCodeAgentExecutionService(
            conversation=conversation,
            role=role,
            conversation_repository=conversation_repo,
            history_service=history_service,
            agent_config_service=agent_config_service,
            additional_tools=additional_tools,
            oauth_service=oauth_service,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported engine: {conversation.engine}",
        )
