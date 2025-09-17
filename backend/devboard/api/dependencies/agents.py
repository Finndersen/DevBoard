from fastapi import Depends

from devboard.agents.llm_service import LLMService
from devboard.agents.project_agent import ProjectAgent
from devboard.agents.task_agent import (
    BaseTaskAgent,
    TaskPlanningAgent,
    TaskSpecificationAgent,
)
from devboard.api.dependencies.entities import get_verified_project, get_verified_task
from devboard.api.dependencies.repositories import (
    get_document_repository,
    get_project_conversation_message_repository,
    get_task_conversation_message_repository,
)
from devboard.api.dependencies.services import (
    get_context_assembly_service,
    get_llm_service,
)
from devboard.db.models import Project, Task
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import (
    DocumentRepository,
    ProjectConversationMessageRepository,
    TaskConversationMessageRepository,
)
from devboard.services.agent_conversation import AgentConversationService
from devboard.services.context_assembly import ContextAssemblyService


def get_project_agent(
    project: Project = Depends(get_verified_project),
    document_repo: DocumentRepository = Depends(get_document_repository),
    context_service: ContextAssemblyService = Depends(get_context_assembly_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> ProjectAgent:
    return ProjectAgent(
        project,
        document_repository=document_repo,
        context_service=context_service,
        llm_service=llm_service,
    )


def get_task_agent(
    task: Task = Depends(get_verified_task),
    document_repo: DocumentRepository = Depends(get_document_repository),
    context_service: ContextAssemblyService = Depends(get_context_assembly_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> BaseTaskAgent:
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
        llm_service=llm_service,
    )


def get_project_agent_conversation_service(
    conversation_repo: ProjectConversationMessageRepository = Depends(get_project_conversation_message_repository),
    project_agent: ProjectAgent = Depends(get_project_agent),
) -> AgentConversationService:
    """Get AgentConversationService instance."""
    return AgentConversationService(agent=project_agent, message_repository=conversation_repo)


def get_task_agent_conversation_service(
    conversation_repo: TaskConversationMessageRepository = Depends(get_task_conversation_message_repository),
    task_agent: BaseTaskAgent = Depends(get_task_agent),
) -> AgentConversationService:
    """Get AgentConversationService instance for task conversations."""
    return AgentConversationService(agent=task_agent, message_repository=conversation_repo)
