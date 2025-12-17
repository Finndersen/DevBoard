"""Repository dependency injection functions."""

from fastapi import Depends
from sqlalchemy.orm import Session

from devboard.db.database import get_db
from devboard.db.repositories import (
    CodebaseRepository,
    ConfigurationRepository,
    ContextProviderResourceRepository,
    ConversationRepository,
    DocumentRepository,
    MCPServerRepository,
    OAuthRepository,
    ProjectRepository,
    TaskRepository,
    WorktreeSlotRepository,
)


def get_codebase_repository(db: Session = Depends(get_db)) -> CodebaseRepository:
    """Get CodebaseRepository instance."""
    return CodebaseRepository(db)


def get_configuration_repository(
    db: Session = Depends(get_db),
) -> ConfigurationRepository:
    """Get ConfigurationRepository instance."""
    return ConfigurationRepository(db)


def get_context_provider_resource_repository(
    db: Session = Depends(get_db),
) -> ContextProviderResourceRepository:
    """Get ContextProviderResourceRepository instance."""
    return ContextProviderResourceRepository(db)


def get_document_repository(db: Session = Depends(get_db)) -> DocumentRepository:
    """Get DocumentRepository instance."""
    return DocumentRepository(db)


def get_project_repository(db: Session = Depends(get_db)) -> ProjectRepository:
    """Get ProjectRepository instance."""
    return ProjectRepository(db)


def get_task_repository(db: Session = Depends(get_db)) -> TaskRepository:
    """Get TaskRepository instance."""
    return TaskRepository(db)


def get_conversation_repository(db: Session = Depends(get_db)) -> ConversationRepository:
    """Get ConversationRepository instance."""
    return ConversationRepository(db)


def get_worktree_slot_repository(db: Session = Depends(get_db)) -> WorktreeSlotRepository:
    """Get WorktreeSlotRepository instance."""
    return WorktreeSlotRepository(db)


def get_oauth_repository(db: Session = Depends(get_db)) -> OAuthRepository:
    """Get OAuthRepository instance."""
    return OAuthRepository(db)


def get_mcp_server_repository(db: Session = Depends(get_db)) -> MCPServerRepository:
    """Get MCPServerRepository instance."""
    return MCPServerRepository(db)
