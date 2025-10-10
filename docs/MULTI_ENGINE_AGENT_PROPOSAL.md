# Multi-Engine Agent Conversation System

## Overview

This document outlines the architecture for extending DevBoard's agent conversation system to support multiple agent engines (PydanticAI, Claude Code, Gemini CLI) while maintaining the existing task lifecycle and conversation management.

## Motivation

The current conversation system is tightly coupled to PydanticAI, storing all messages in the database. To support external agent engines like Claude Code and Gemini CLI that manage their own sessions, we need:

1. **Multiple conversations per task** - One conversation per task lifecycle phase (DEFINING, PLANNING, IMPLEMENTING, etc.)
2. **External session management** - Store session IDs for external agents rather than message content
3. **Engine restrictions by role** - Enforce which engines can be used for different agent purposes
4. **Phase-based archiving** - Clean slate for each task phase while preserving history

## Core Concepts

### Agent Engine vs Agent Role

**Agent Engine** - The underlying technology/framework that powers the agent:
- `PYDANTIC_AI` - Internal framework with tool approval, stores messages in DB
- `CLAUDE_CODE` - Anthropic's CLI tool with full capabilities, stores sessions in JSONL
- `GEMINI_CLI` - Google's CLI tool (future support)

**Agent Role** - The agent's purpose/responsibility (derived from task status):
- `PROJECT` - Project-level Q&A (PROJECT context, any task status)
- `TASK_SPECIFICATION` - Defining task requirements (TASK context, DEFINING status)
- `TASK_PLANNING` - Creating implementation plans (TASK context, PLANNING status)
- `TASK_IMPLEMENTATION` - Writing code (TASK context, IMPLEMENTING status)

### Conversation Lifecycle

Each task phase gets its own conversation:

\`\`\`
DEFINING phase → Conversation #1 (active)
  ↓ transition validates specification exists
PLANNING phase → Conversation #1 (archived), Conversation #2 (active)
  ↓ transition validates plan exists
IMPLEMENTING phase → Conversation #2 (archived), Conversation #3 (active)
  ↓ transition validates implementation complete
REVIEWING phase → Conversation #3 (archived), Conversation #4 (active)
\`\`\`

**Key properties**:
- Only one active conversation per task at a time
- Previous conversations archived (is_active=False) during phase transition
- Archived conversations remain queryable for history
- Each conversation stores its engine type and external session ID if applicable

## Schema Changes

### Conversation Model

\`\`\`python
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int]
    parent_entity_type: Mapped[ParentEntityType]  # PROJECT or TASK
    parent_entity_id: Mapped[int]

    # New fields
    engine: Mapped[AgentEngine]  # Which engine powers this conversation
    external_session_id: Mapped[str | None]  # For Claude Code/Gemini sessions
    is_active: Mapped[bool] = mapped_column(default=True)  # Current vs archived
    archived_at: Mapped[datetime | None]

    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Indexes
    __table_args__ = (
        Index('idx_active_conversations', 'parent_entity_type', 'parent_entity_id', 'is_active'),
    )
\`\`\`

**Migration notes**:
- Remove `uq_one_conversation_per_entity` unique constraint
- Default existing rows: `engine=PYDANTIC_AI`, `is_active=True`

### ConversationMessage Model (unchanged)

Messages continue to be stored only for PydanticAI conversations. External engine conversations reference their session files via `external_session_id`.

## Agent Engine System

Following the pattern established in `backend/devboard/agents/language_models.py`, create `backend/devboard/agents/agent_engines.py`:

### Engine Definitions

\`\`\`python
from enum import Enum
from dataclasses import dataclass

class AgentEngine(str, Enum):
    """Available agent engines."""
    PYDANTIC_AI = "pydantic_ai"
    CLAUDE_CODE = "claude_code"
    GEMINI_CLI = "gemini_cli"

@dataclass
class AgentEngineDefinition:
    """Definition of an agent engine with its capabilities."""
    engine: AgentEngine
    display_name: str
    description: str
    available_models: list[str]  # Format: "provider:model"
    supports_tool_approval: bool
    stores_messages_in_db: bool

# Global registry of all engines
ALL_ENGINES: list[AgentEngineDefinition] = [
    AgentEngineDefinition(
        engine=AgentEngine.PYDANTIC_AI,
        display_name="PydanticAI",
        description="Internal agent framework with tool approval",
        available_models=[
            "anthropic:claude-opus-4",
            "anthropic:claude-sonnet-4",
            "openai:gpt-4o",
            "gemini:gemini-2.0-flash-exp",
        ],
        supports_tool_approval=True,
        stores_messages_in_db=True,
    ),
    AgentEngineDefinition(
        engine=AgentEngine.CLAUDE_CODE,
        display_name="Claude Code",
        description="Anthropic's official CLI with full capabilities",
        available_models=[
            "anthropic:claude-opus-4",
            "anthropic:claude-sonnet-4",
        ],
        supports_tool_approval=False,
        stores_messages_in_db=False,
    ),
    AgentEngineDefinition(
        engine=AgentEngine.GEMINI_CLI,
        display_name="Gemini CLI",
        description="Google's Gemini command-line interface",
        available_models=[
            "gemini:gemini-2.0-flash-exp",
            "gemini:gemini-pro",
        ],
        supports_tool_approval=False,
        stores_messages_in_db=False,
    ),
]

# Default engines by agent role
RECOMMENDED_AGENT_ENGINES: dict[AgentRole, AgentEngine] = {
    AgentRole.PROJECT: AgentEngine.PYDANTIC_AI,
    AgentRole.TASK_SPECIFICATION: AgentEngine.PYDANTIC_AI,
    AgentRole.TASK_PLANNING: AgentEngine.PYDANTIC_AI,
    AgentRole.TASK_IMPLEMENTATION: AgentEngine.CLAUDE_CODE,
}

# Engine restrictions by agent role
ALLOWED_ENGINES_BY_ROLE: dict[AgentRole, list[AgentEngine]] = {
    AgentRole.PROJECT: [AgentEngine.PYDANTIC_AI],
    AgentRole.TASK_SPECIFICATION: [AgentEngine.PYDANTIC_AI],
    AgentRole.TASK_PLANNING: [AgentEngine.PYDANTIC_AI],
    AgentRole.TASK_IMPLEMENTATION: [AgentEngine.CLAUDE_CODE, AgentEngine.GEMINI_CLI],
}

class AgentEngineRepository:
    """Repository for querying agent engine capabilities."""

    @staticmethod
    def get_engine_definition(engine: AgentEngine) -> AgentEngineDefinition:
        """Get definition for a specific engine."""
        for defn in ALL_ENGINES:
            if defn.engine == engine:
                return defn
        raise ValueError(f"Unknown engine: {engine}")

    @staticmethod
    def get_available_engines_for_role(role: AgentRole) -> list[AgentEngineDefinition]:
        """Get all engines allowed for a given agent role."""
        allowed = ALLOWED_ENGINES_BY_ROLE.get(role, [])
        return [defn for defn in ALL_ENGINES if defn.engine in allowed]

    @staticmethod
    def get_default_engine_for_role(role: AgentRole) -> AgentEngine:
        """Get recommended engine for a given agent role."""
        return RECOMMENDED_AGENT_ENGINES.get(role, AgentEngine.PYDANTIC_AI)

    @staticmethod
    def validate_engine_for_role(engine: AgentEngine, role: AgentRole) -> bool:
        """Check if engine is allowed for given role."""
        allowed = ALLOWED_ENGINES_BY_ROLE.get(role, [])
        return engine in allowed

    @staticmethod
    def get_available_models_for_engine(engine: AgentEngine) -> list[str]:
        """Get list of available models for an engine."""
        defn = AgentEngineRepository.get_engine_definition(engine)
        return defn.available_models
\`\`\`

## Configuration System

### Agent Configuration Schema

Update `backend/devboard/config/agent_config.py`:

\`\`\`python
class AgentConfig(BaseSettings):
    """Base configuration for agents."""

    selected_engine: AgentEngine | None = None  # Override default engine
    selected_model: str | None = None  # Override default model

    @property
    def model_hierarchy(self) -> ModelPreference:
        """Get effective model preference for this agent."""
        # Implementation determines model from selected_model or defaults
        ...

class QAAgentConfig(AgentConfig):
    """Configuration for Q&A agent (PROJECT role)."""
    pass

class SpecificationAgentConfig(AgentConfig):
    """Configuration for specification agent (TASK_SPECIFICATION role)."""
    pass

class PlanningAgentConfig(AgentConfig):
    """Configuration for planning agent (TASK_PLANNING role)."""
    pass

class ImplementationAgentConfig(AgentConfig):
    """Configuration for implementation agent (TASK_IMPLEMENTATION role)."""
    pass
\`\`\`

**Configuration hierarchy**:
1. User selects engine (optional) → validates against role's allowed engines
2. User selects model (optional) → validates against engine's available models
3. System uses role's default engine if not specified
4. System uses engine's default model if not specified

**Validation** (performed in service layer, not config):
\`\`\`python
def validate_agent_configuration(role: AgentRole, config: AgentConfig):
    """Validate that configuration is valid for the role."""
    engine = config.selected_engine or AgentEngineRepository.get_default_engine_for_role(role)

    # Validate engine allowed for role
    if not AgentEngineRepository.validate_engine_for_role(engine, role):
        raise ValueError(f"Engine {engine} not allowed for role {role}")

    # Validate model available for engine
    if config.selected_model:
        available = AgentEngineRepository.get_available_models_for_engine(engine)
        if config.selected_model not in available:
            raise ValueError(f"Model {config.selected_model} not available for engine {engine}")
\`\`\`

## Phase Transition Workflow

### Transition Process

When a task transitions between lifecycle phases (e.g., DEFINING → PLANNING):

1. **Validate transition is allowed**
   - Check task status permits transition
   - Validate phase-specific requirements (e.g., specification exists before planning)

2. **Finalize current phase**
   - Send finalization prompt to active conversation (hardcoded for now)
   - Example: "The planning phase is complete. Please provide a final summary."

3. **Archive current conversation**
   - Set `is_active = False`
   - Set `archived_at = now()`

4. **Create new conversation for next phase**
   - Automatically determine appropriate engine for new role
   - Create new Conversation with `is_active = True`
   - Generate external session ID if needed

### Validation Rules

\`\`\`python
class TaskPhaseTransitionService:
    """Service for managing task phase transitions."""

    @staticmethod
    def can_transition_to_phase(task: Task, target_status: TaskStatus) -> tuple[bool, str]:
        """Check if task can transition to target phase."""

        if target_status == TaskStatus.PLANNING:
            # Must have specification content
            if not task.specification or not task.specification.strip():
                return False, "Cannot transition to PLANNING without specification"

        elif target_status == TaskStatus.IMPLEMENTING:
            # Must have implementation plan
            if not task.implementation_plan or not task.implementation_plan.strip():
                return False, "Cannot transition to IMPLEMENTING without implementation plan"

        # Add more validations as needed

        return True, ""
\`\`\`

### Service Integration

Create `backend/devboard/services/conversation_service.py`:

\`\`\`python
class ConversationService:
    """Unified service for managing conversations across all engines."""

    def __init__(self, db: Session):
        self.db = db
        self.conversation_repo = ConversationRepository(db)

    async def get_conversation_messages(
        self,
        conversation: Conversation,
        project: Project | None = None,
    ) -> list[ConversationMessage]:
        """Retrieve messages for a conversation regardless of engine."""

        if conversation.engine == AgentEngine.PYDANTIC_AI:
            # Query database for messages
            return self.conversation_repo.get_messages(conversation.id)

        elif conversation.engine == AgentEngine.CLAUDE_CODE:
            # Use ClaudeCodeSessionService to read JSONL
            if not project:
                raise ValueError("Project required for Claude Code sessions")

            service = ClaudeCodeSessionService(Path(project.working_directory))
            return service.load_conversation_history(conversation.external_session_id)

        elif conversation.engine == AgentEngine.GEMINI_CLI:
            # Future: Implement Gemini session loading
            raise NotImplementedError("Gemini CLI not yet supported")

        else:
            raise ValueError(f"Unknown engine: {conversation.engine}")

    async def archive_and_create_new_for_phase_transition(
        self,
        task: Task,
        new_status: TaskStatus,
    ) -> Conversation:
        """Archive current conversation and create new one for next phase."""

        # Get current active conversation
        current = self.conversation_repo.get_active_conversation_for_entity(
            ParentEntityType.TASK,
            task.id
        )

        # Send finalization prompt to current conversation
        if current:
            await self._send_phase_finalization_prompt(current, task, new_status)

            # Archive current conversation
            self.conversation_repo.archive_conversation(current.id)

        # Determine engine for new phase
        role = self._get_role_for_task_status(new_status)
        engine = AgentEngineRepository.get_default_engine_for_role(role)

        # Create new conversation
        return self.conversation_repo.create_conversation_for_task_phase(
            task_id=task.id,
            engine=engine,
        )

    def _get_role_for_task_status(self, status: TaskStatus) -> AgentRole:
        """Derive agent role from task status."""
        mapping = {
            TaskStatus.DEFINING: AgentRole.TASK_SPECIFICATION,
            TaskStatus.PLANNING: AgentRole.TASK_PLANNING,
            TaskStatus.IMPLEMENTING: AgentRole.TASK_IMPLEMENTATION,
            TaskStatus.REVIEWING: AgentRole.TASK_IMPLEMENTATION,  # Same agent
        }
        return mapping.get(status, AgentRole.TASK_SPECIFICATION)

    async def _send_phase_finalization_prompt(
        self,
        conversation: Conversation,
        task: Task,
        new_status: TaskStatus,
    ):
        """Send finalization prompt to conversation before archiving."""
        # Hardcoded for now, will be configurable later
        prompts = {
            TaskStatus.PLANNING: "The specification phase is complete. Please provide a final summary.",
            TaskStatus.IMPLEMENTING: "The planning phase is complete. Please provide a final summary.",
            TaskStatus.REVIEWING: "The implementation phase is complete. Please provide a final summary.",
        }
        prompt = prompts.get(new_status, "This phase is complete.")

        # Send prompt based on engine type
        # Implementation depends on engine
        pass
\`\`\`

## Repository Updates

Update `backend/devboard/db/repositories/conversation.py`:

\`\`\`python
class ConversationRepository:
    """Repository for conversation database operations."""

    def get_active_conversation_for_entity(
        self,
        parent_type: ParentEntityType,
        parent_id: int,
    ) -> Conversation | None:
        """Get the currently active conversation for an entity."""
        return self.db.query(Conversation).filter(
            Conversation.parent_entity_type == parent_type,
            Conversation.parent_entity_id == parent_id,
            Conversation.is_active == True,
        ).first()

    def create_conversation_for_task_phase(
        self,
        task_id: int,
        engine: AgentEngine,
    ) -> Conversation:
        """Create a new conversation for a task phase."""

        # Generate external session ID if needed
        external_session_id = None
        if engine == AgentEngine.CLAUDE_CODE:
            external_session_id = str(uuid.uuid4())
        elif engine == AgentEngine.GEMINI_CLI:
            external_session_id = str(uuid.uuid4())

        conversation = Conversation(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=task_id,
            engine=engine,
            external_session_id=external_session_id,
            is_active=True,
        )

        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        return conversation

    def archive_conversation(self, conversation_id: int):
        """Archive a conversation by setting is_active=False."""
        conversation = self.db.query(Conversation).get(conversation_id)
        if conversation:
            conversation.is_active = False
            conversation.archived_at = datetime.now(timezone.utc)
            self.db.commit()
\`\`\`

## API Changes

### No New Endpoints Required

The existing endpoints continue to work with minimal changes:

**GET /api/tasks/{task_id}/conversation/messages**
- Automatically uses `ConversationService.get_conversation_messages()`
- Returns messages from active conversation only
- Works transparently across all engines

**POST /api/tasks/{task_id}/conversation/messages**
- Sends message to active conversation
- Router determines engine and uses appropriate agent

**Phase transition** happens automatically via existing task status update endpoint:
\`\`\`
PATCH /api/tasks/{task_id}
{
  "status": "PLANNING"  // Triggers archive + new conversation
}
\`\`\`

### Modified Router Logic

Update `backend/devboard/api/routers/conversations.py`:

\`\`\`python
@router.get("/tasks/{task_id}/conversation/messages")
async def get_task_conversation_messages(
    task_id: int,
    db: Session = Depends(get_db),
) -> list[ConversationMessageOut]:
    """Get messages from the task's active conversation."""

    # Get task and project
    task = task_repo.get_by_id(task_id)
    project = project_repo.get_by_id(task.project_id)

    # Get active conversation
    conversation_service = ConversationService(db)
    conversation = conversation_service.conversation_repo.get_active_conversation_for_entity(
        ParentEntityType.TASK,
        task_id,
    )

    if not conversation:
        return []

    # Get messages (works for all engines)
    messages = await conversation_service.get_conversation_messages(conversation, project)

    return [ConversationMessageOut.from_orm(msg) for msg in messages]
\`\`\`

## Implementation Order

1. **Create `backend/devboard/agents/agent_engines.py`**
   - Define AgentEngine enum
   - Create engine definitions and repository
   - Define role mappings and restrictions

2. **Database Migration**
   - Add new columns to conversations table
   - Update indexes
   - Set defaults for existing data

3. **Update Models**
   - Add new fields to Conversation model
   - Update relationships if needed

4. **Update Configuration**
   - Add selected_engine to AgentConfig
   - Keep selected_model field

5. **Create Services**
   - ConversationService for unified message retrieval
   - TaskPhaseTransitionService for validation

6. **Update Repositories**
   - Add new query methods to ConversationRepository

7. **Update Routers**
   - Modify conversation endpoints to use ConversationService
   - Add phase transition handling to task status updates

8. **Add Tests**
   - Unit tests for all new components
   - Integration tests for phase transitions
   - Test engine validation and restrictions

## Future Enhancements

- **Configurable finalization prompts** - Move hardcoded prompts to configuration
- **UI for archived conversations** - Allow viewing conversation history per phase
- **Gemini CLI integration** - Add support when Gemini CLI is available
- **Cross-conversation context** - Allow referencing archived conversations
- **Manual conversation archiving** - UI for archiving without phase transition
- **Conversation branching** - Support multiple active conversations per task
