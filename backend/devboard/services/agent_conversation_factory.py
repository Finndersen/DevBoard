"""Factory for creating agent conversation services based on engine type."""

import logging

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.agent_engines import AgentEngine
from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.claude_code.agent_conversation import ClaudeCodeConversationService
from devboard.agents.claude_code.task_agent import ClaudeTaskPlanningAgent, ClaudeTaskSpecificationAgent
from devboard.agents.internal.agent_conversation import PydanticAIConversationService
from devboard.agents.internal.task_agent import TaskPlanningAgent, TaskSpecificationAgent
from devboard.agents.types import AgentRole
from devboard.db.models.task import Task
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.document import DocumentRepository
from devboard.services.context_assembly import ContextAssemblyService

logger = logging.getLogger(__name__)


def create_task_conversation_service(
    conversation_id: int,
    task: Task,
    agent_role: AgentRole,
    agent_engine: AgentEngine,
    conversation_repo: ConversationRepository,
    document_repo: DocumentRepository,
    context_service: ContextAssemblyService,
    agent_config_service: AgentConfigService,
) -> BaseAgentConversationService:
    """Create a task conversation service based on agent role and engine.

    Args:
        conversation_id: ID of the conversation
        task: Task model instance
        agent_role: Agent role (e.g., TASK_SPECIFICATION, TASK_PLANNING)
        agent_engine: Agent engine to use (e.g., INTERNAL, CLAUDE_CODE)
        conversation_repo: Conversation repository
        document_repo: Document repository
        context_service: Context assembly service
        agent_config_service: Service for agent engine and model config

    Returns:
        Configured conversation service instance

    Raises:
        ValueError: If role/engine combination is not supported
    """
    if agent_engine == AgentEngine.INTERNAL:
        # Create PydanticAI agent based on role
        if agent_role == AgentRole.TASK_SPECIFICATION:
            agent = TaskSpecificationAgent(
                task=task,
                document_repository=document_repo,
                context_service=context_service,
                agent_config_service=agent_config_service,
            )
        elif agent_role == AgentRole.TASK_PLANNING:
            agent = TaskPlanningAgent(
                task=task,
                document_repository=document_repo,
                context_service=context_service,
                agent_config_service=agent_config_service,
            )
        else:
            raise ValueError(f"Unsupported agent role for PydanticAI: {agent_role}")

        return PydanticAIConversationService(
            conversation_id=conversation_id,
            agent=agent,
            conversation_repository=conversation_repo,
        )

    elif agent_engine == AgentEngine.CLAUDE_CODE:
        # Fetch conversation instance for session tracking
        conversation = conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Create Claude Code agent based on role
        if agent_role == AgentRole.TASK_SPECIFICATION:
            agent = ClaudeTaskSpecificationAgent(
                task=task,
                document_repository=document_repo,
            )
        elif agent_role == AgentRole.TASK_PLANNING:
            agent = ClaudeTaskPlanningAgent(
                task=task,
                document_repository=document_repo,
            )
        else:
            raise ValueError(f"Unsupported agent role for Claude Code: {agent_role}")

        return ClaudeCodeConversationService(
            conversation=conversation,
            agent=agent,
            conversation_repository=conversation_repo,
        )

    else:
        raise ValueError(f"Unsupported agent engine: {agent_engine}")
