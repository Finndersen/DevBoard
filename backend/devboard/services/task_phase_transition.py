"""Service for managing task phase transitions and validation.

Handles validation rules for transitioning between task lifecycle phases
and ensures required content exists before proceeding to the next phase.
Also manages conversation lifecycle during phase transitions.
"""

import uuid

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.agent_engines import AgentEngine
from devboard.agents.types import AgentEngineModelConfig, AgentRole
from devboard.db.models import ParentEntityType
from devboard.db.models.task import Task, TaskStatus
from devboard.db.repositories.conversation import ConversationRepository


class TaskPhaseTransitionService:
    """Service for managing task phase transitions and conversation lifecycle."""

    def __init__(
        self,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
    ):
        """Initialize service.

        Args:
            conversation_repo: Repository for conversation operations
            agent_config_service: Service for agent configuration
        """
        self.conversation_repo = conversation_repo
        self.agent_config_service = agent_config_service

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
            if not task.specification or not task.specification.strip():
                return False, "Cannot transition to PLANNING without specification content"

        # PLANNING → IMPLEMENTING
        elif target_status == TaskStatus.IMPLEMENTING:
            if not task.implementation_plan or not task.implementation_plan.strip():
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
        config_dict = self.agent_config_service.get_agent_configuration(agent_role)
        config = AgentEngineModelConfig.from_dict(config_dict["config"])

        # Generate external session ID if needed
        external_session_id = None
        if config.engine in [AgentEngine.CLAUDE_CODE, AgentEngine.GEMINI_CLI]:
            external_session_id = str(uuid.uuid4())

        # Create conversation with config snapshot
        return self.conversation_repo.create(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task.id,
            agent_role=agent_role,
            engine=config.engine,
            model_id=config.model_id,
            external_session_id=external_session_id,
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
