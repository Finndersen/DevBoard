"""Project API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

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
    get_conversation_service,
    get_project_service,
    get_task_git_service,
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
from devboard.api.schemas.conversation import ConversationResponse, CreateConversationResponse
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
from devboard.db.repositories.conversation import NoActiveConversationError
from devboard.services.conversation_service import ConversationService
from devboard.services.project_service import ProjectService
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_service import TaskService

router = APIRouter()


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """List all projects."""
    projects = project_repo.get_all()
    return projects


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    project_service: ProjectService = Depends(get_project_service),
    project_repo: ProjectRepository = Depends(get_project_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    custom_field_repo: CustomFieldRepository = Depends(get_custom_field_repository),
):
    """Create a new project with initial conversation."""
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

    # Create project using service (creates project + document + conversation)
    created_project = project_service.create_project(
        name=project.name,
        description=project.description,
        custom_fields=project.custom_fields,
    )
    project_repo.db.commit()
    project_repo.db.refresh(created_project)

    # Get the conversation that was just created
    conversation = conversation_repo.get_most_recent_conversation_for_entity(
        ParentEntityType.PROJECT, created_project.id
    )

    return ProjectResponse(
        id=created_project.id,
        name=created_project.name,
        description=created_project.description,
        created_at=created_project.created_at,
        specification_document_id=created_project.specification.id,
        default_conversation_id=conversation.id if conversation else None,
        custom_fields=created_project.custom_fields,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    project: Project = Depends(get_verified_project),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> ProjectResponse:
    """Get a specific project with active conversation_id."""
    conversation = conversation_repo.get_most_recent_conversation_for_entity(ParentEntityType.PROJECT, project_id)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        specification_document_id=project.specification.id,
        default_conversation_id=conversation.id if conversation else None,
        custom_fields=project.custom_fields,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    project: Project = Depends(get_verified_project),
    document_repo: DocumentRepository = Depends(get_document_repository),
):
    """Update a project and its specification content."""
    update_data = project_update.model_dump(exclude_unset=True)

    # Handle specification content update separately
    specification = update_data.pop("specification", None)
    if specification is not None:
        # Update the specification document content
        document_repo.update_content(project.specification, specification)

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

    # Update other project fields
    for field, value in update_data.items():
        setattr(project, field, value)

    return project


@router.delete("/{project_id}", response_model=DeleteResponse)
async def delete_project(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """Delete a project."""
    deleted = project_repo.delete_by_id(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

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
) -> CreateConversationResponse:
    """Create a new conversation for a project."""
    result = conversation_service.create_project_conversation(project_id)
    conv = result.conversation
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

    # Get conversations for all tasks
    task_responses: list[TaskResponse] = []
    for task in tasks:
        # TODO: Make SimpleTaskResponse model with limited fields for list view
        try:
            conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, task.id)
        except NoActiveConversationError:
            # Skip tasks without conversations (legacy data)
            continue

        task_responses.append(
            TaskResponse(
                id=task.id,
                title=task.title,
                project_id=task.project_id,
                codebase_id=task.codebase_id,
                status=task.status,
                conversation_id=conversation.id,
                created_at=task.created_at,
                specification_document_id=task.specification.id,
                implementation_plan_document_id=task.implementation_plan.id if task.implementation_plan else None,
                custom_fields=task.custom_fields,
            )
        )

    return task_responses


@router.post("/{project_id}/tasks", response_model=TaskResponse)
async def create_project_task(
    project_id: int,
    task: TaskCreateNested,
    task_service: TaskService = Depends(get_task_service),
    task_git_service: TaskGitService = Depends(get_task_git_service),
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
    project_repo: ProjectRepository = Depends(get_project_repository),
):
    """Create a new task under a project with initial conversation."""

    # Verify project exists
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    codebase = get_verified_codebase(task.codebase_id, codebase_repo)

    # Validate mandatory custom fields
    mandatory_fields = task_service.get_mandatory_custom_fields()
    if mandatory_fields:
        custom_fields = task.custom_fields or {}
        missing_fields = []
        for field in mandatory_fields:
            if field.name not in custom_fields or custom_fields[field.name] is None or custom_fields[field.name] == "":
                missing_fields.append(field.name)
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required custom fields: {', '.join(missing_fields)}",
            )

    # Use provided base_branch or fall back to codebase's default_branch
    base_branch = task.base_branch or codebase.default_branch

    # Create task using service (creates task + documents + conversation)
    # Tasks always start in PLANNING status
    created_task = task_service.create_task(
        project_id=project_id,
        title=task.title,
        codebase_id=task.codebase_id,
        specification_content=task.specification_content or "",
        branch_name=task.branch_name,
        base_branch=base_branch,
        custom_fields=task.custom_fields,
    )

    # Create git branch immediately to ensure consistent codebase view during planning
    # Branch name will be auto-generated if not provided
    await task_git_service.ensure_task_branch(created_task)

    # Get the active conversation that was just created
    # Will raise NoActiveConversationError if not found
    conversation = conversation_repo.get_active_conversation_for_entity(ParentEntityType.TASK, created_task.id)

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
