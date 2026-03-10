from fastapi import Depends, HTTPException

from devboard.api.dependencies.repositories import (
    get_codebase_repository,
    get_conversation_repository,
    get_document_repository,
    get_mcp_server_repository,
    get_project_repository,
    get_task_repository,
    get_worktree_slot_repository,
)
from devboard.db.models import Codebase, Conversation, Document, MCPServerConfig, Project, Task, WorktreeSlot
from devboard.db.repositories import (
    CodebaseRepository,
    ConversationRepository,
    DocumentRepository,
    MCPServerRepository,
    ProjectRepository,
    TaskRepository,
    WorktreeSlotRepository,
)


def get_verified_project(
    project_id: int,
    project_repo: ProjectRepository = Depends(get_project_repository),
) -> Project:
    """Get a project by ID, raising 404 if not found."""
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_verified_task(
    task_id: int,
    task_repo: TaskRepository = Depends(get_task_repository),
) -> Task:
    """Get a task by ID, raising 404 if not found."""
    task = task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def get_verified_codebase(
    codebase_id: int,
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
) -> Codebase:
    """Get a codebase by ID, raising 404 if not found."""
    codebase = codebase_repo.get_by_id(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")
    return codebase


def get_verified_conversation(
    conversation_id: int,
    conversation_repo: ConversationRepository = Depends(get_conversation_repository),
) -> Conversation:
    """Get a conversation by ID, raising 404 if not found."""
    conversation = conversation_repo.get_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def get_verified_document(
    document_id: int,
    document_repo: DocumentRepository = Depends(get_document_repository),
) -> Document:
    """Get a document by ID, raising 404 if not found."""
    document = document_repo.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def get_verified_mcp_server_config(
    server_id: int,
    mcp_server_repo: MCPServerRepository = Depends(get_mcp_server_repository),
) -> MCPServerConfig:
    """Get an MCP server configuration by ID, raising 404 if not found."""
    mcp_server_config = mcp_server_repo.get_by_id(server_id)
    if not mcp_server_config:
        raise HTTPException(status_code=404, detail="MCP server config not found")
    return mcp_server_config


def get_verified_worktree_slot(
    slot_id: int,
    worktree_slot_repo: WorktreeSlotRepository = Depends(get_worktree_slot_repository),
) -> WorktreeSlot:
    """Get a worktree slot by ID, raising 404 if not found."""
    slot = worktree_slot_repo.get_by_id(slot_id)
    if not slot:
        raise HTTPException(status_code=404, detail="Worktree slot not found")
    return slot
