"""Repository dependency injection functions."""

from fastapi import Depends
from sqlalchemy.orm import Session

from devboard.db.database import get_db
from devboard.db.repositories import (
    CodebaseRepository,
    ConfigurationRepository,
    ContextProviderResourceRepository,
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.db.repositories.conversation_message import (
    ProjectConversationMessageRepository,
    TaskConversationMessageRepository,
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


def get_project_conversation_message_repository(
    db: Session = Depends(get_db),
) -> ProjectConversationMessageRepository:
    """Get ProjectConversationMessageRepository instance."""
    return ProjectConversationMessageRepository(db)


def get_task_conversation_message_repository(
    db: Session = Depends(get_db),
) -> TaskConversationMessageRepository:
    """Get TaskConversationMessageRepository instance."""
    return TaskConversationMessageRepository(db)
