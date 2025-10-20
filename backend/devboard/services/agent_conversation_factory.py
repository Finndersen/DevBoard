"""Factory for creating agent conversation services based on engine type."""

from devboard.agents.base_agent_conversation import BaseAgentConversationService
from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.engines.claude_code import (
    ClaudeCodeConversationService,
    ClaudeImplementationAgent,
    ClaudeTaskPlanningAgent,
    ClaudeTaskSpecificationAgent,
)
from devboard.agents.engines.internal import PydanticAIConversationService, TaskPlanningAgent, TaskSpecificationAgent
from devboard.agents.language_models import llm_registry
from devboard.agents.roles.types import AgentRole
from devboard.db.models import Conversation, Task
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.document import DocumentRepository
from devboard.services.context_assembly import ContextAssemblyService


def create_task_conversation_service(
    conversation: Conversation,
    task: Task,
    conversation_repo: ConversationRepository,
    document_repo: DocumentRepository,
    context_service: ContextAssemblyService,
) -> BaseAgentConversationService:
    """Create a task conversation service based on agent role and engine.

    Args:
        conversation: Conversation model instance
        task: Task model instance
        conversation_repo: Conversation repository
        document_repo: Document repository
        context_service: Context assembly service

    Returns:
        Configured conversation service instance

    Raises:
        ValueError: If role/engine combination is not supported
    """
    # Extract agent role and engine from conversation
    agent_role = conversation.agent_role
    agent_engine = conversation.engine
    model_id = conversation.model_id
    model = llm_registry.get(model_id)
    # TODO: I think it actually makes more sense for ConversationService to construct its own agent, but not sure about
    # a sensible way of handling dependencies. For now, we'll pass them in here.
    if agent_engine == AgentEngine.INTERNAL:
        # Create PydanticAI agent based on role
        if agent_role == AgentRole.TASK_SPECIFICATION:
            agent = TaskSpecificationAgent(
                task=task,
                document_repository=document_repo,
                context_service=context_service,
                model=model,
            )
        elif agent_role == AgentRole.TASK_PLANNING:
            agent = TaskPlanningAgent(
                task=task,
                document_repository=document_repo,
                context_service=context_service,
                model=model,
            )
        else:
            raise ValueError(f"Unsupported agent role for PydanticAI: {agent_role}")

        return PydanticAIConversationService(
            conversation=conversation,
            agent=agent,
            conversation_repository=conversation_repo,
        )

    elif agent_engine == AgentEngine.CLAUDE_CODE:
        # Create Claude Code agent based on role
        # Pass the conversation's external_session_id to resume previous conversations
        session_id = conversation.external_session_id

        if agent_role == AgentRole.TASK_SPECIFICATION:
            agent = ClaudeTaskSpecificationAgent(
                task=task,
                document_repository=document_repo,
                model=model,
                session_id=session_id,
            )
        elif agent_role == AgentRole.TASK_PLANNING:
            agent = ClaudeTaskPlanningAgent(
                task=task,
                document_repository=document_repo,
                model=model,
                session_id=session_id,
            )
        elif agent_role == AgentRole.TASK_IMPLEMENTATION:
            agent = ClaudeImplementationAgent(
                task=task,
                document_repository=document_repo,
                model=model,
                session_id=session_id,
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
