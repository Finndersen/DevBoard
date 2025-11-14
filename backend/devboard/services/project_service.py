"""Service for managing project lifecycle operations.

Handles project creation and conversation lifecycle management.
Ensures proper agent configuration for project-level conversations.
"""

from devboard.agents.role_types import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.project import Project
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.services.conversation_service import ConversationService


class ProjectService:
    """Service for project lifecycle operations."""

    def __init__(
        self,
        conversation_service: ConversationService,
        document_repo: DocumentRepository,
        project_repo: ProjectRepository,
    ):
        """Initialize service.

        Args:
            conversation_service: Service for conversation operations
            document_repo: Repository for document operations
            project_repo: Repository for project operations
        """
        self.conversation_service = conversation_service
        self.document_repo = document_repo
        self.project_repo = project_repo

    def create_project(
        self,
        name: str,
        description: str | None = None,
    ) -> Project:
        """Create a new project with initial conversation.

        Creates the project entity, specification document, and an initial active
        conversation configured with the appropriate agent for project management.

        Args:
            name: Project name
            description: Optional project description

        Returns:
            Created Project instance with active conversation
        """
        # Create specification document
        specification_doc = self.document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")

        # Create project using repository
        project = self.project_repo.create(
            name=name,
            description=description,
            specification=specification_doc,
        )

        # Create initial conversation
        self.conversation_service.create_initial_conversation_for_parent_entity(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=project.id,
            agent_role=AgentRoleType.PROJECT,
        )

        return project
