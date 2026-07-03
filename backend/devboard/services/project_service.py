"""Service for managing project lifecycle operations.

Handles project creation and conversation lifecycle management.
Ensures proper agent configuration for project-level conversations.
"""

from typing import Any

from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.project import Project
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.services.conversation_service import ConversationService
from devboard.services.project_directory import ensure_project_directory
from devboard.services.system_event_emitter import SystemEventEmitter


class ProjectService:
    """Service for project lifecycle operations."""

    def __init__(
        self,
        conversation_service: ConversationService,
        document_repo: DocumentRepository,
        project_repo: ProjectRepository,
        system_event_emitter: SystemEventEmitter,
    ):
        self.conversation_service = conversation_service
        self.document_repo = document_repo
        self.project_repo = project_repo
        self.system_event_emitter = system_event_emitter

    def validate_parent(self, parent_project_id: int) -> None:
        """Validate parent project constraints for a new initiative.

        Args:
            parent_project_id: ID of the proposed parent project

        Raises:
            ValueError: If the parent is invalid (not found, or itself an initiative)
        """
        parent = self.project_repo.get_by_id(parent_project_id)
        if not parent:
            raise ValueError(f"Parent project {parent_project_id} not found")
        if parent.parent_project_id is not None:
            raise ValueError("Cannot nest more than one level deep: the target parent is already an initiative")

    def create_project(
        self,
        name: str,
        description: str | None = None,
        custom_fields: dict[str, Any] | None = None,
        parent_project_id: int | None = None,
    ) -> Project:
        """Create a new project with initial conversation.

        Creates the project entity, specification document, and an initial active
        conversation configured with the appropriate agent for project management.

        Args:
            name: Project name
            description: Optional project description
            custom_fields: Optional custom field values
            parent_project_id: Optional parent project ID (makes this an initiative)

        Returns:
            Created Project instance with active conversation
        """
        if parent_project_id is not None:
            self.validate_parent(parent_project_id)

        # Create specification/context document — type reflects whether this is an initiative
        document_type = DocumentType.for_project(is_initiative=parent_project_id is not None)
        specification_doc = self.document_repo.create(document_type, "")

        # Create project using repository
        project = self.project_repo.create(
            name=name,
            description=description,
            specification=specification_doc,
            custom_fields=custom_fields,
            parent_project_id=parent_project_id,
        )

        # Create project working directory eagerly
        ensure_project_directory(project)

        # Create initial conversation
        self.conversation_service.create_initial_conversation_for_parent_entity(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=project.id,
            agent_role=AgentRoleType.PROJECT,
        )

        self.system_event_emitter.emit_project_created(project)

        return project
