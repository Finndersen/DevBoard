from fastapi import Depends

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.internal.agent_conversation import PydanticAIConversationService
from devboard.agents.internal.base_agent import BaseAgent
from devboard.agents.internal.project_agent import ProjectAgent
from devboard.agents.internal.task_agent import (
    BaseTaskAgent,
    TaskPlanningAgent,
    TaskSpecificationAgent,
)
from devboard.api.dependencies.repositories import (
    get_conversation_repository,
    get_document_repository,
    get_project_repository,
    get_task_repository,
)
from devboard.api.dependencies.services import (
    get_agent_config_service,
    get_context_assembly_service,
)
from devboard.db.models import ParentEntityType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import (
    ConversationRepository,
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.services.context_assembly import ContextAssemblyService


def get_conversation_agent(
    conversation_id: int,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    context_service: ContextAssemblyService = Depends(get_context_assembly_service),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
) -> BaseAgent:
    """Get the appropriate agent for a conversation based on its parent entity."""

    conversation = conversation_repo.get_by_id(conversation_id)
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found")

    if conversation.parent_entity_type == ParentEntityType.PROJECT:
        project = project_repo.get_by_id(conversation.parent_entity_id)
        if not project:
            raise ValueError(f"Project {conversation.parent_entity_id} not found")

        return ProjectAgent(
            project,
            document_repository=document_repo,
            context_service=context_service,
            agent_config_service=agent_config_service,
        )

    elif conversation.parent_entity_type == ParentEntityType.TASK:
        task = task_repo.get_by_id(conversation.parent_entity_id)
        if not task:
            raise ValueError(f"Task {conversation.parent_entity_id} not found")

        agent_type: type[BaseTaskAgent]
        if task.status == TaskStatus.DEFINING:
            agent_type = TaskSpecificationAgent
        elif task.status == TaskStatus.PLANNING:
            agent_type = TaskPlanningAgent
        else:
            raise ValueError(f"Task in state {task.status} cannot accept agent messages")

        return agent_type(
            task=task,
            document_repository=document_repo,
            context_service=context_service,
            agent_config_service=agent_config_service,
        )

    # Future: Add other entity types (codebase, etc.)
    else:
        raise ValueError(f"Unknown entity type: {conversation.parent_entity_type}")


def get_conversation_service(
    conversation_id: int,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    agent: BaseAgent = Depends(get_conversation_agent),
) -> PydanticAIConversationService:
    """Get conversation service with appropriate agent."""
    return PydanticAIConversationService(
        conversation_id=conversation_id, agent=agent, conversation_repository=conversation_repo
    )
