"""Shared logic for assembling agent configuration for a conversation."""

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles import AgentRole
from devboard.api.schemas.agent_config import AgentConfigResponse, ToolInfo
from devboard.db.models import Conversation, Project, Task
from devboard.db.models.codebase import Codebase
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.integration_service import IntegrationService
from devboard.services.project_directory import ensure_project_directory
from devboard.services.task_service import TaskService


async def assemble_agent_config(
    conversation: Conversation,
    document_repo: DocumentRepository,
    agent_config_service: AgentConfigService,
    integration_service: IntegrationService,
    task_service: TaskService,
    conversation_repo: ConversationRepository,
) -> AgentConfigResponse:
    """Assemble the full agent configuration for a conversation.

    Resolves the working directory, creates the agent role, gathers tools,
    and returns the complete AgentConfigResponse.
    """
    parent = conversation.get_parent_entity()
    # Working dir should not matter or be used since the role is not actually used for execution here
    if isinstance(parent, Task):
        working_dir = parent.codebase.local_path
    elif isinstance(parent, Project):
        working_dir = str(ensure_project_directory(parent))
    elif isinstance(parent, Codebase):
        working_dir = parent.local_path
    else:
        working_dir = "."

    # Lazy import to break circular dependency:
    # factories -> background_agent -> tools -> conversation_tools -> agent_config_assembly -> factories
    from devboard.api.dependencies.factories import create_agent_role_for_conversation  # noqa: PLC0415

    role: AgentRole = await create_agent_role_for_conversation(
        conversation=conversation,
        document_repo=document_repo,
        agent_config_service=agent_config_service,
        integration_service=integration_service,
        task_service=task_service,
        conversation_repo=conversation_repo,
        working_dir=working_dir,
    )

    agent_config = agent_config_service.get_agent_configuration(conversation.agent_role)

    role_tools = [
        ToolInfo(
            name=tool.name,
            description=tool.description,
            input_schema=tool.function_schema.json_schema,
            source="role",
        )
        for tool in role.get_tools()
    ]

    mcp_tools = [
        ToolInfo(
            name=mcp_tool.name,
            description=mcp_tool.description,
            input_schema=mcp_tool.input_schema,
            source="mcp",
            server_name=mcp_tool.server.name,
        )
        for mcp_tool in agent_config_service.get_enabled_mcp_tools(conversation.agent_role)
    ]

    builtin_tools = [ToolInfo(name=name, source="builtin") for name in role.allowed_builtin_tools]

    return AgentConfigResponse(
        agent_role=conversation.agent_role.value,
        behaviour_guidelines=role.get_system_prompt(),
        context_content=await role.get_context_content(),
        custom_instructions=agent_config.custom_instructions,
        role_tools=role_tools,
        mcp_tools=mcp_tools,
        builtin_tools=builtin_tools,
    )
