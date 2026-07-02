"""Project API endpoints."""

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.language_models import ModelType
from devboard.agents.roles import AgentRoleType
from devboard.agents.title_generator import (
    TaskGenerationResult,
    generate_conversation_title,
    generate_task_title_and_branch,
)
from devboard.api.dependencies.entities import get_verified_codebase, get_verified_project
from devboard.api.dependencies.repositories import (
    get_codebase_repository,
    get_conversation_repository,
    get_custom_field_repository,
    get_document_repository,
    get_project_repository,
    get_task_repository,
)
from devboard.api.dependencies.services import (
    get_agent_config_service,
    get_conversation_service,
    get_project_service,
    get_system_event_emitter,
    get_task_service,
)
from devboard.api.schemas import (
    CodebaseResponse,
    DeleteResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    TaskCreateNested,
    TaskResponse,
)
from devboard.api.schemas.conversation import (
    ConversationResponse,
    CreateConversationResponse,
    CreateProjectConversationRequest,
)
from devboard.db.models import ParentEntityType
from devboard.db.models.enums import EntityType
from devboard.db.models.project import Project
from devboard.db.repositories import (
    CodebaseRepository,
    ConversationRepository,
    CustomFieldRepository,
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.services.conversation_service import ConversationService
from devboard.services.project_service import ProjectService
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_service import TaskService

router = APIRouter()


async def _resolve_model_id_override(
    model_type: str | None,
    title_result: TaskGenerationResult | None,
    initial_message: str | None,
    agent_config_service: AgentConfigService,
) -> str | None:
    """Resolve a model_id override from a model_type string.

    Returns None when model_type is not specified (use role default).
    """
    if model_type is None:
        return None
    effective_config = agent_config_service.get_effective_config(AgentRoleType.TASK_PLANNING)
    if model_type == "auto":
        if title_result is not None:
            auto_model_type = title_result.model_type
        elif initial_message is not None:
            auto_result = await generate_task_title_and_branch(initial_message)
            auto_model_type = auto_result.model_type
        else:
            return None
    else:
        auto_model_type = ModelType(model_type)
    return agent_config_service.get_model_id_for_type(auto_model_type, effective_config.engine)


def _build_project_response(project: Project, conversation_id: int | None = None) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        specification_document_id=project.specification.id,
        default_conversation_id=conversation_id,
        custom_fields=project.custom_fields,
        parent_project_id=project.parent_project_id,
        parent_project_name=project.parent_project_name,
        complete=project.complete,
    )


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    parent_project_id: int | None = Query(None),
    complete: bool | None = Query(None),
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """List projects with optional hierarchy and completion filters.

    By default, only non-complete projects are returned. Pass complete=true to get completed ones.
    Pass parent_project_id to list initiatives under a specific project.
    """
    projects = project_repo.get_all(parent_project_id=parent_project_id, complete=complete)
    return [_build_project_response(p) for p in projects]


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    project_service: ProjectService = Depends(get_project_service),
    project_repo: ProjectRepository = Depends(get_project_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    custom_field_repo: CustomFieldRepository = Depends(get_custom_field_repository),
):
    """Create a new project (or initiative when parent_project_id is provided)."""
    mandatory_fields = custom_field_repo.get_mandatory_fields(entity_type=EntityType.PROJECT)
    if mandatory_fields:
        custom_fields = project.custom_fields or {}
        missing_fields = [
            field.name
            for field in mandatory_fields
            if field.name not in custom_fields or custom_fields[field.name] is None or custom_fields[field.name] == ""
        ]
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required custom fields: {', '.join(missing_fields)}",
            )

    try:
        created_project = project_service.create_project(
            name=project.name,
            description=project.description,
            custom_fields=project.custom_fields,
            parent_project_id=project.parent_project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    project_repo.db.commit()
    project_repo.db.refresh(created_project)

    # Get the conversation that was just created
    conversation = conversation_repo.get_most_recent_conversation_for_entity(
        ParentEntityType.PROJECT, created_project.id
    )

    return _build_project_response(created_project, conversation_id=conversation.id if conversation else None)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    project: Project = Depends(get_verified_project),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> ProjectResponse:
    """Get a specific project with active conversation_id."""
    conversation = conversation_repo.get_most_recent_conversation_for_entity(ParentEntityType.PROJECT, project_id)
    return _build_project_response(project, conversation_id=conversation.id if conversation else None)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    project: Project = Depends(get_verified_project),
    project_repo: ProjectRepository = Depends(get_project_repository),
    document_repo: DocumentRepository = Depends(get_document_repository),
    system_event_emitter: SystemEventEmitter = Depends(get_system_event_emitter),
    project_service: ProjectService = Depends(get_project_service),
):
    """Update a project and its specification content."""
    update_data = project_update.model_dump(exclude_unset=True)
    changed_fields = list(update_data.keys())

    # Handle specification content update separately
    specification = update_data.pop("specification", None)
    if specification is not None:
        document_repo.update_content(project.specification, specification)

    # Validate and apply parent_project_id update
    if "parent_project_id" in update_data:
        new_parent_id = update_data.pop("parent_project_id")
        if new_parent_id is not None:
            if project.initiatives:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot make a project with initiatives into an initiative itself",
                )
            try:
                project_service.validate_parent(new_parent_id, project_id=project_id)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
        project.parent_project_id = new_parent_id
        # Expire the cached parent relationship so parent_project_name is fresh
        project_repo.db.expire(project, ["parent"])

    # Handle custom fields with merge semantics: merge provided fields, remove keys set to None
    custom_fields = update_data.pop("custom_fields", None)
    if custom_fields is not None:
        merged = dict(project.custom_fields or {})
        for key, value in custom_fields.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        project.custom_fields = merged

    # Update remaining project fields (name, description, etc.), excluding None for non-nullable columns
    for field, value in update_data.items():
        if value is not None:
            setattr(project, field, value)

    system_event_emitter.emit_project_updated(project, changed_fields)

    return _build_project_response(project)


@router.delete("/{project_id}", response_model=DeleteResponse)
async def delete_project(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repository),
    system_event_emitter: SystemEventEmitter = Depends(get_system_event_emitter),
):
    """Delete a project."""
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.initiatives:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a project that has initiatives. Delete or re-parent the initiatives first.",
        )

    project_name = project.name
    system_event_emitter.emit_project_deleted(project_id, project_name)

    project_repo.delete_by_id(project_id)
    project_repo.db.commit()
    return {"message": "Project deleted successfully", "success": True}


# Project Conversation Endpoints
@router.get("/{project_id}/conversations", response_model=list[ConversationResponse])
async def list_project_conversations(
    project_id: int,
    project: Project = Depends(get_verified_project),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> list[ConversationResponse]:
    """List all active conversations for a project."""
    conversations = conversation_repo.get_active_conversations_for_entity(ParentEntityType.PROJECT, project_id)
    return [
        ConversationResponse(
            id=conv.id,
            parent_entity_type=conv.parent_entity_type,
            parent_entity_id=conv.parent_entity_id,
            agent_role=conv.agent_role,
            engine=conv.engine,
            model_id=conv.model_id,
            is_active=conv.is_active,
            external_session_id=conv.external_session_id,
            title=conv.title,
            last_activity_at=conv.last_activity_at,
            created_at=conv.created_at,
            parent_entity_name=project.name,
        )
        for conv in conversations
    ]


@router.post("/{project_id}/conversations", response_model=CreateConversationResponse)
async def create_project_conversation(
    project_id: int,
    project: Project = Depends(get_verified_project),
    conversation_service: ConversationService = Depends(get_conversation_service),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    request: CreateProjectConversationRequest | None = Body(default=None),
) -> CreateConversationResponse:
    """Create a new conversation for a project with optional initial message."""
    result = conversation_service.create_project_conversation(project_id)
    conv = result.conversation

    if request and request.initial_message:
        title = await generate_conversation_title(request.initial_message)
        conversation_repo.update_title(conv, title)
        conversation_repo.db.commit()

        execution_manager = get_execution_manager()
        execution_manager.start_agent_execution(conv.id, request.initial_message)

    return CreateConversationResponse(
        id=conv.id,
        parent_entity_type=conv.parent_entity_type,
        parent_entity_id=conv.parent_entity_id,
        agent_role=conv.agent_role,
        engine=conv.engine,
        model_id=conv.model_id,
        is_active=conv.is_active,
        external_session_id=conv.external_session_id,
        title=conv.title,
        created_at=conv.created_at,
        at_cap=result.at_cap,
    )


# Project Task Endpoints
@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
async def list_project_tasks(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """List all tasks for a project."""
    # Verify project exists
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = task_repo.get_for_project(project_id)

    conversations = conversation_repo.get_active_conversations_for_entities(
        entity_type=ParentEntityType.TASK,
        entity_ids=[task.id for task in tasks],
    )
    task_conv_map: dict[int, int] = {}
    for conv in conversations:
        if conv.parent_entity_id not in task_conv_map:
            task_conv_map[conv.parent_entity_id] = conv.id

    task_responses: list[TaskResponse] = []
    for task in tasks:
        # TODO: Make SimpleTaskResponse model with limited fields for list view
        conversation_id = task_conv_map.get(task.id)
        if conversation_id is None:
            # Skip tasks without conversations (legacy data)
            continue

        task_responses.append(
            TaskResponse(
                id=task.id,
                title=task.title,
                project_id=task.project_id,
                codebase_id=task.codebase_id,
                status=task.status,
                conversation_id=conversation_id,
                created_at=task.created_at,
                specification_document_id=task.specification_id,
                implementation_plan_document_id=task.implementation_plan_id,
                custom_fields=task.custom_fields,
            )
        )

    return task_responses


@router.post("/{project_id}/tasks", response_model=TaskResponse)
async def create_project_task(
    project_id: int,
    task: TaskCreateNested,
    task_service: TaskService = Depends(get_task_service),
    conversation_service: ConversationService = Depends(get_conversation_service),
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
    agent_config_service: AgentConfigService = Depends(get_agent_config_service),
):
    """Create a new task under a project with initial conversation."""

    # Verify project exists
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    codebase = get_verified_codebase(task.codebase_id, codebase_repo)

    # Use provided base_branch or fall back to codebase's default_branch
    base_branch = task.base_branch or codebase.default_branch

    # Generate title and branch name if title not provided
    title_result: TaskGenerationResult | None = None
    if task.title is None:
        if task.initial_message is None:
            raise HTTPException(status_code=400, detail="Either title or initial_message must be provided")

        title_result = await generate_task_title_and_branch(task.initial_message)
        task_title = title_result.title
        task_branch_name = task.branch_name or title_result.branch_name
    else:
        task_title = task.title
        task_branch_name = task.branch_name

    # Resolve model_id override from model_type
    resolved_model_id = await _resolve_model_id_override(
        task.model_type, title_result, task.initial_message, agent_config_service
    )

    # Create task using service (creates task + documents + conversation)
    # Tasks always start in PLANNING status
    created_task = await task_service.create_task(
        project_id=project_id,
        title=task_title,
        codebase_id=task.codebase_id,
        specification_content=task.specification_content or "",
        branch_name=task_branch_name,
        base_branch=base_branch,
        custom_fields=task.custom_fields,
        model_id_override=resolved_model_id,
    )

    # Get the active conversation that was just created
    # Will raise NoActiveConversationError if not found
    conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, created_task.id)

    # If initial message provided, start agent execution and set conversation title
    if task.initial_message is not None:
        # Commit before starting background execution so the new DB session
        # opened by the execution manager can see the task and conversation
        conversation_repo.commit()

        try:
            get_execution_manager().start_agent_execution(conversation.id, task.initial_message)
            # Set conversation title to the task title (AI-generated or user-provided)
            conversation_repo.update_title(conversation, task_title)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start agent execution: {e}") from e

    return TaskResponse(
        id=created_task.id,
        title=created_task.title,
        project_id=created_task.project_id,
        codebase_id=created_task.codebase_id,
        status=created_task.status,
        conversation_id=conversation.id,
        created_at=created_task.created_at,
        specification_document_id=created_task.specification.id,
        implementation_plan_document_id=(
            created_task.implementation_plan.id if created_task.implementation_plan else None
        ),
        custom_fields=created_task.custom_fields,
    )


# Project Codebase Endpoints
@router.get("/{project_id}/codebases", response_model=list[CodebaseResponse])
async def list_project_codebases(
    project_id: int,
    project: Project = Depends(get_verified_project),
):
    """List all codebases linked to a project."""
    return project.codebases


@router.post("/{project_id}/codebases/{codebase_id}", response_model=CodebaseResponse)
async def link_codebase_to_project(
    project_id: int,
    codebase_id: int,
    project: Project = Depends(get_verified_project),
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
):
    """Link a codebase to a project."""
    codebase = codebase_repo.get_by_id(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    # Check if already linked
    if codebase in project.codebases:
        raise HTTPException(status_code=409, detail="Codebase is already linked to this project")

    project.codebases.append(codebase)
    codebase_repo.db.commit()
    codebase_repo.db.refresh(codebase)

    return codebase


@router.delete("/{project_id}/codebases/{codebase_id}", response_model=DeleteResponse)
async def unlink_codebase_from_project(
    project_id: int,
    codebase_id: int,
    project: Project = Depends(get_verified_project),
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
):
    """Unlink a codebase from a project."""
    codebase = codebase_repo.get_by_id(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")

    if codebase not in project.codebases:
        raise HTTPException(status_code=404, detail="Codebase is not linked to this project")

    project.codebases.remove(codebase)
    codebase_repo.db.commit()

    return {"message": "Codebase unlinked successfully", "success": True}
