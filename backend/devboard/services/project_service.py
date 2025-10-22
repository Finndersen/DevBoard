"""Service for managing project lifecycle operations.

Handles project creation and conversation lifecycle management.
Ensures proper agent configuration for project-level conversations.
"""

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.types import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.project import Project
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.project import ProjectRepository


class ProjectService:
    """Service for project lifecycle operations."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        document_repo: DocumentRepository,
        project_repo: ProjectRepository,
        agent_config_service: AgentConfigService,
    ):
        """Initialize service.

        Args:
            conversation_repo: Repository for conversation operations
            document_repo: Repository for document operations
            project_repo: Repository for project operations
            agent_config_service: Service for agent configuration
        """
        self.conversation_repo = conversation_repo
        self.document_repo = document_repo
        self.project_repo = project_repo
        self.agent_config_service = agent_config_service

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

        # Get effective config for PROJECT role
        config = self.agent_config_service.get_effective_config(AgentRoleType.PROJECT)

        # Create initial conversation (external_session_id will be set later if needed)
        self.conversation_repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=project.id,
            agent_role=AgentRoleType.PROJECT,
            engine=config.engine,
            model_id=config.model_id,
            external_session_id=None,
            is_active=True,
        )

        return project
