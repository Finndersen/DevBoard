"""Service for managing project lifecycle operations.

Handles project creation and conversation lifecycle management.
Ensures proper agent configuration for project-level conversations.
"""

from typing import Any

from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.initiative import Initiative
from devboard.db.models.project import Project
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.initiative import InitiativeRepository
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
        initiative_repo: InitiativeRepository,
        system_event_emitter: SystemEventEmitter,
    ):
        self.conversation_service = conversation_service
        self.document_repo = document_repo
        self.project_repo = project_repo
        self.initiative_repo = initiative_repo
        self.system_event_emitter = system_event_emitter

    def create_project(
        self,
        name: str,
        description: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> Project:
        """Create a new project with initial conversation.

        Creates the project entity, specification document, and an initial active
        conversation configured with the appropriate agent for project management.

        Args:
            name: Project name
            description: Optional project description
            custom_fields: Optional custom field values

        Returns:
            Created Project instance with active conversation
        """
        specification_doc = self.document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")

        project = self.project_repo.create(
            name=name,
            description=description,
            specification=specification_doc,
            custom_fields=custom_fields,
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

    def create_initiative(self, project_id: int, name: str, description: str) -> Initiative:
        """Create a new initiative under a project.

        Args:
            project_id: ID of the parent project
            name: Initiative name
            description: Initiative description

        Returns:
            Created Initiative instance

        Raises:
            ValueError: If the parent project is not found
        """
        project = self.project_repo.get_by_id(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        specification_doc = self.document_repo.create(DocumentType.INITIATIVE_CONTEXT, "")
        initiative = self.initiative_repo.create(
            name=name,
            description=description,
            specification=specification_doc,
            project_id=project_id,
        )
        self.system_event_emitter.emit_initiative_created(initiative)
        return initiative

    def get_initiative(self, initiative_id: int) -> Initiative | None:
        """Get an initiative by ID."""
        return self.initiative_repo.get_by_id(initiative_id)

    def complete_project(self, project: Project, summary: str) -> Project:
        """Mark a project as complete.

        Args:
            project: The project to complete
            summary: A summary of what was accomplished

        Returns:
            Updated Project instance with complete=True
        """
        project.complete = True
        updated = self.project_repo.update(project)
        self.system_event_emitter.emit_project_completed(updated, summary)
        return updated

    def complete_initiative(self, initiative: Initiative, summary: str) -> Initiative:
        """Mark an initiative as complete.

        Args:
            initiative: The initiative to complete
            summary: A summary of what was accomplished

        Returns:
            Updated Initiative instance with complete=True
        """
        initiative.complete = True
        updated = self.initiative_repo.update(initiative)
        self.system_event_emitter.emit_initiative_completed(updated, summary)
        return updated
