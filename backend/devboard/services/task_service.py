"""Service for managing task lifecycle operations.

Handles task creation, phase transitions, and conversation lifecycle management.
Ensures proper agent configuration and conversation state throughout the task lifecycle.
"""

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.types import AgentRole
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.document import DocumentRepository
from devboard.db.repositories.task import TaskRepository


class TaskService:
    """Service for task lifecycle operations including creation and phase transitions."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        document_repo: DocumentRepository,
        task_repo: TaskRepository,
        agent_config_service: AgentConfigService,
    ):
        """Initialize service.

        Args:
            conversation_repo: Repository for conversation operations
            document_repo: Repository for document operations
            task_repo: Repository for task operations
            agent_config_service: Service for agent configuration
        """
        self.conversation_repo = conversation_repo
        self.document_repo = document_repo
        self.task_repo = task_repo
        self.agent_config_service = agent_config_service

    def create_task(
        self,
        project_id: int,
        title: str,
        status: TaskStatus = TaskStatus.DEFINING,
        codebase_id: int | None = None,
        remote_task_id: str | None = None,
        specification_content: str = "",
    ) -> Task:
        """Create a new task with initial conversation.

        Creates the task entity, required documents, and an initial active conversation
        configured with the appropriate agent role, engine, and model based on the
        task's initial status.

        Args:
            project_id: ID of the project this task belongs to
            title: Task title
            status: Initial task status (defaults to DEFINING)
            codebase_id: Optional codebase ID
            remote_task_id: Optional remote task identifier (e.g., Jira issue key)
            specification_content: Initial content for the specification document (defaults to empty string)

        Returns:
            Created Task instance with active conversation
        """
        # Create documents
        specification_doc = self.document_repo.create(DocumentType.TASK_SPECIFICATION, specification_content)

        # Create task using repository (implementation plan will be created later when needed)
        task = self.task_repo.create(
            project_id=project_id,
            title=title,
            specification=specification_doc,
            implementation_plan=None,
            status=status,
            codebase_id=codebase_id,
            remote_task_id=remote_task_id,
        )

        # Determine agent role from status
        agent_role = self._get_agent_role_for_status(status)

        # Get effective config for role
        config = self.agent_config_service.get_effective_config(agent_role)

        # Create initial conversation (external_session_id will be set later if needed)
        self.conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task.id,
            agent_role=agent_role,
            engine=config.engine,
            model_id=config.model_id,
            external_session_id=None,
            is_active=True,
        )

        return task

    @staticmethod
    def can_transition_to_phase(task: Task, target_status: TaskStatus) -> tuple[bool, str]:
        """Check if task can transition to target phase.

        Validates that required content exists before allowing phase transition.
        Each phase has specific prerequisites:
        - PLANNING: Requires specification content
        - IMPLEMENTING: Requires implementation plan
        - REVIEWING: Implementation must be marked complete
        - COMPLETE: All work must be finished

        Args:
            task: The task to validate
            target_status: The target status to transition to

        Returns:
            Tuple of (can_transition, error_message)
            - can_transition: True if transition is allowed
            - error_message: Empty string if allowed, error description otherwise
        """
        # DEFINING → PLANNING
        if target_status == TaskStatus.PLANNING:
            if not task.specification or not task.specification.content.strip():
                return False, "Cannot transition to PLANNING without specification content"

        # PLANNING → IMPLEMENTING
        elif target_status == TaskStatus.IMPLEMENTING:
            if not task.implementation_plan or not task.implementation_plan.content.strip():
                return False, "Cannot transition to IMPLEMENTING without implementation plan"

        # IMPLEMENTING → REVIEWING
        elif target_status == TaskStatus.REVIEWING:
            # Could add checks for implementation completion markers
            # For now, allow transition if explicitly requested
            pass

        # REVIEWING → COMPLETE
        elif target_status == TaskStatus.COMPLETE:
            # Could add checks for review completion
            # For now, allow transition if explicitly requested
            pass

        # DEFINING is initial state, always allowed
        elif target_status == TaskStatus.DEFINING:
            pass

        return True, ""

    @staticmethod
    def get_finalization_prompt(target_status: TaskStatus) -> str:
        """Get the finalization prompt for transitioning to a new phase.

        Hardcoded for now, will be configurable in the future.

        Args:
            target_status: The target status being transitioned to

        Returns:
            Finalization prompt to send to current conversation
        """
        prompts = {
            TaskStatus.PLANNING: "The specification phase is complete. Please provide a final summary of the task requirements and any important considerations for the planning phase.",
            TaskStatus.IMPLEMENTING: "The planning phase is complete. Please provide a final summary of the implementation plan and any important notes for the implementation phase.",
            TaskStatus.REVIEWING: "The implementation phase is complete. Please provide a final summary of what was implemented and any important notes for review.",
            TaskStatus.COMPLETE: "The review phase is complete. Please provide a final summary of the task completion.",
        }
        return prompts.get(target_status, "This phase is complete. Please provide a final summary.")

    def create_conversation_for_task_phase(
        self,
        task: Task,
        new_status: TaskStatus,
    ):
        """Create conversation for task phase with appropriate agent config.

        Archives current conversation if exists, derives agent role from status,
        gets effective config from AgentConfigService, and creates new conversation
        with config snapshot.

        Args:
            task: The task transitioning phases
            new_status: The new status being transitioned to

        Returns:
            New Conversation instance for the phase
        """
        # Archive current conversation
        current = self.conversation_repo.get_active_for_entity(ParentEntityType.TASK, task.id)
        if current:
            self.conversation_repo.archive(current.id)

        # Derive agent role from task status
        agent_role = self._get_agent_role_for_status(new_status)

        # Get effective config for role
        agent_config = self.agent_config_service.get_agent_configuration(agent_role)
        config = agent_config.config

        # Create conversation with config snapshot (external_session_id will be set later if needed)
        return self.conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task.id,
            agent_role=agent_role,
            engine=config.engine,
            model_id=config.model_id,
            external_session_id=None,
        )

    @staticmethod
    def _get_agent_role_for_status(status: TaskStatus) -> AgentRole:
        """Map task status to agent role.

        Args:
            status: Task status

        Returns:
            Corresponding AgentRole
        """
        mapping = {
            TaskStatus.DEFINING: AgentRole.TASK_SPECIFICATION,
            TaskStatus.PLANNING: AgentRole.TASK_PLANNING,
            TaskStatus.IMPLEMENTING: AgentRole.TASK_IMPLEMENTATION,
            TaskStatus.REVIEWING: AgentRole.TASK_IMPLEMENTATION,  # Same agent for review
        }
        return mapping.get(status, AgentRole.TASK_SPECIFICATION)
