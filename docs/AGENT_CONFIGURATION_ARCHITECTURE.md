# Agent Configuration Architecture

## Overview

This document describes DevBoard's agent configuration system, which supports multiple agent engines (execution frameworks) with role-based restrictions and per-conversation configuration snapshots.

## Core Concepts

### Agent Role vs Agent Engine

**Agent Role** - The agent's purpose/responsibility in the system:
- `PROJECT` - Project-level Q&A and documentation management
- `TASK_SPECIFICATION` - Task requirements definition
- `TASK_PLANNING` - Implementation plan creation
- `TASK_IMPLEMENTATION` - Code implementation and execution
- `INVESTIGATION` - Codebase analysis and context gathering

**Agent Engine** - The underlying execution framework:
- `INTERNAL` - DevBoard's internal agent framework (PydanticAI under the hood)
- `CLAUDE_CODE` - Anthropic's Claude Code CLI
- `GEMINI_CLI` - Google's Gemini CLI (future support)

### Configuration Hierarchy

The system follows a three-layer hierarchy:

```
Agent Role → Agent Engine → Model
     ↓             ↓            ↓
  PROJECT    →   INTERNAL   →  anthropic:claude-opus-4
                               anthropic:claude-sonnet-4
                               openai:gpt-4o
                               gemini:gemini-2.0-flash-exp
```

**Key Rules**:
1. Each agent role has **allowed engines** (security/capability restrictions)
2. Each engine has **available models** (framework support)
3. Available models are further filtered by **configured providers** (API keys present)

### Role-Based Engine Restrictions

Different agent roles have different engine requirements:

| Agent Role | Allowed Engines | Reason |
|------------|----------------|---------|
| PROJECT | INTERNAL only | Requires tool approval for safe project operations |
| TASK_SPECIFICATION | INTERNAL only | Requires tool approval for document editing |
| TASK_PLANNING | INTERNAL only | Requires tool approval for plan creation |
| TASK_IMPLEMENTATION | CLAUDE_CODE, GEMINI_CLI | Needs full IDE capabilities (file ops, shell, git) |
| INVESTIGATION | INTERNAL only | Requires tool approval for codebase analysis |

**Rationale**:
- PROJECT/SPECIFICATION/PLANNING agents modify project artifacts and need user approval for safety
- IMPLEMENTATION agents need full system access and can use external CLI tools
- INVESTIGATION agents analyze code and need controlled tool execution

### Configuration Levels

The system maintains configuration at two levels:

#### 1. Role-Level Configuration (Defaults)
Stored in `AgentConfig` (database configuration):
- `selected_engine: AgentEngine | None` - User's preferred engine override
- `selected_model: str | None` - User's preferred model override

When `null`, system uses recommended defaults for the role.

#### 2. Conversation-Level Configuration (Snapshots)
Stored on `Conversation` model:
- `agent_role: str` - **Immutable** - Agent role for this conversation
- `engine: AgentEngine` - **Immutable** - Engine powering this conversation
- `model_id: str` - **Mutable** - Model being used (can be changed within same engine)

When a conversation is created, it snapshots the current effective configuration for its role.

### Configuration Resolution

Effective configuration is resolved using this precedence:

```python
# For a given agent role:
effective_engine = selected_engine OR recommended_engine_for_role
effective_model = selected_model OR default_model_for_engine
```

Example for `TASK_IMPLEMENTATION` role:
1. User hasn't configured anything → Use `CLAUDE_CODE` + `anthropic:claude-opus-4` (defaults)
2. User selected `GEMINI_CLI` → Use `GEMINI_CLI` + `gemini:gemini-2.0-flash-exp` (user's engine, engine's default model)
3. User selected `CLAUDE_CODE` + `anthropic:claude-sonnet-4` → Use both (fully customized)

## Data Structures

### AgentEngineModelConfig

Unified data structure for engine + model configuration:

```python
from dataclasses import dataclass
from devboard.agents.agent_engines import AgentEngine

@dataclass
class AgentEngineModelConfig:
    """Combined engine and model configuration."""
    engine: AgentEngine
    model_id: str

    def to_dict(self) -> dict:
        return {
            "engine": self.engine.value,
            "model_id": self.model_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentEngineModelConfig":
        return cls(
            engine=AgentEngine(data["engine"]),
            model_id=data["model_id"]
        )
```

This structure is used throughout the system:
- Service layer passes it between methods
- API endpoints convert to/from JSON
- Configuration resolution returns it
- Conversation creation uses it

### Database Schema

#### Conversation Model

```python
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Polymorphic association to parent entity
    parent_entity_type: Mapped[ParentEntityType]
    parent_entity_id: Mapped[int]

    # Agent configuration snapshot (set at creation, immutable except model_id)
    agent_role: Mapped[str] = mapped_column(nullable=False)  # AgentRole enum value
    engine: Mapped[AgentEngine] = mapped_column(SQLEnum(AgentEngine), nullable=False)
    model_id: Mapped[str] = mapped_column(nullable=False)  # e.g., "anthropic:claude-sonnet-4"

    # External session management
    external_session_id: Mapped[str | None] = mapped_column(nullable=True)

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(default=True)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(default=now_utc, onupdate=now_utc)
```

**Field Mutability**:
- `agent_role` - **Immutable** (new conversation for role change)
- `engine` - **Immutable** (can't switch PydanticAI ↔ Claude Code mid-conversation)
- `model_id` - **Mutable** (can change Opus ↔ Sonnet within same engine)

**Why Immutable Engine?**
- PydanticAI stores messages in database
- Claude Code stores messages in JSONL files
- Gemini CLI has its own session format
- Switching engines mid-conversation would break message history

**Why Mutable Model?**
- Same engine, different model is safe (e.g., Opus → Sonnet in Claude Code)
- Allows optimizing cost/performance mid-conversation
- Messages remain in same storage format

## Service Layer

### AgentConfigService

Central service for agent configuration management (renamed from LLMService):

```python
class AgentConfigService:
    """Service for managing agent engine and model configuration."""

    def __init__(
        self,
        config_service: ConfigService,
        llm_repository: LLMRepository,
        engine_repository: AgentEngineRepository,
    ):
        self.config_service = config_service
        self.llm_repository = llm_repository
        self.engine_repository = engine_repository
```

**Key Methods**:

#### get_agent_configuration(agent_role: AgentRole) → dict
Returns role-level configuration with effective values and available options:
```json
{
  "agent_role": "task_implementation",
  "config": {
    "engine": "claude_code",
    "model_id": "anthropic:claude-sonnet-4"
  },
  "available_engines": [
    {
      "engine": "claude_code",
      "display_name": "Claude Code",
      "description": "Anthropic's official CLI with full capabilities"
    },
    {
      "engine": "gemini_cli",
      "display_name": "Gemini CLI",
      "description": "Google's Gemini command-line interface"
    }
  ]
}
```

#### get_available_models_by_engine() → dict
Returns all available models grouped by engine:
```json
{
  "internal": [
    {"id": "anthropic:claude-opus-4", "provider": "anthropic", "name": "claude-opus-4", "model_type": "large"},
    {"id": "openai:gpt-4o", "provider": "openai", "name": "gpt-4o", "model_type": "large"}
  ],
  "claude_code": [
    {"id": "anthropic:claude-opus-4", "provider": "anthropic", "name": "claude-opus-4", "model_type": "large"},
    {"id": "anthropic:claude-sonnet-4", "provider": "anthropic", "name": "claude-sonnet-4", "model_type": "medium"}
  ],
  "gemini_cli": [
    {"id": "gemini:gemini-2.0-flash-exp", "provider": "gemini", "name": "gemini-2.0-flash-exp", "model_type": "medium"}
  ]
}
```

#### update_agent_configuration(agent_role, config: AgentEngineModelConfig) → dict
Updates role-level configuration with validation:
1. Validates engine is allowed for role
2. Validates model is available for engine (provider configured)
3. Updates `AgentConfig` with `selected_engine` and `selected_model`
4. Returns updated configuration (same format as `get_agent_configuration`)

### ConversationRepository

Low-level repository for conversation CRUD operations:

```python
class ConversationRepository:
    """Repository for conversation database operations."""

    def create(
        self,
        parent_entity_type: ParentEntityType,
        parent_entity_id: int,
        agent_role: AgentRole,
        engine: AgentEngine,
        model_id: str,
        external_session_id: str | None = None,
        is_active: bool = True,
    ) -> Conversation:
        """Create conversation with all parameters specified."""

    def update_model(self, conversation_id: int, model_id: str) -> Conversation:
        """Update model for a conversation (must be compatible with engine)."""

    def archive(self, conversation_id: int) -> None:
        """Archive a conversation (set is_active=False)."""

    def get_active_for_entity(
        self,
        parent_type: ParentEntityType,
        parent_id: int
    ) -> Conversation | None:
        """Get active conversation for an entity."""
```

**Design Philosophy**: Repository only handles data operations. Business logic lives in service layer.

### TaskPhaseTransitionService

Higher-level service for conversation lifecycle management:

```python
class TaskPhaseTransitionService:
    """Service for managing task phase transitions and conversation lifecycle."""

    def create_conversation_for_task_phase(
        self,
        task: Task,
        new_status: TaskStatus,
    ) -> Conversation:
        """Create conversation for task phase with appropriate agent config."""
        # 1. Archive current conversation
        # 2. Derive agent role from task status
        # 3. Get effective config for role
        # 4. Generate external session ID if needed
        # 5. Create conversation with config snapshot
```

**Conversation Creation Flow**:
1. Archive current active conversation (if exists)
2. Map task status → agent role (e.g., PLANNING → TASK_PLANNING)
3. Get effective engine + model from `AgentConfigService`
4. Generate external session ID for Claude Code/Gemini CLI
5. Call `ConversationRepository.create()` with all parameters

**Agent Role Mapping**:
```python
TaskStatus.DEFINING → AgentRole.TASK_SPECIFICATION
TaskStatus.PLANNING → AgentRole.TASK_PLANNING
TaskStatus.IMPLEMENTING → AgentRole.TASK_IMPLEMENTATION
TaskStatus.REVIEWING → AgentRole.TASK_IMPLEMENTATION  # Same agent
```

## API Design

### Agent Configuration Endpoints

#### GET /api/agents/{agent_role}/configuration
Get role-level configuration.

**Response**: `AgentConfigurationResponse`
```json
{
  "agent_role": "task_implementation",
  "config": {
    "engine": "claude_code",
    "model_id": "anthropic:claude-sonnet-4"
  },
  "available_engines": [
    {"engine": "claude_code", "display_name": "Claude Code", "description": "..."},
    {"engine": "gemini_cli", "display_name": "Gemini CLI", "description": "..."}
  ]
}
```

#### PUT /api/agents/{agent_role}/configuration
Update role-level configuration.

**Request**: `UpdateAgentConfigurationRequest`
```json
{
  "engine": "claude_code",
  "model_id": "anthropic:claude-opus-4"
}
```

**Response**: Same as GET (updated configuration)

**Validation**:
- Engine must be allowed for role (400 error if not)
- Model must be available for engine (400 error if not)

#### GET /api/agents/available-models
Get all available models grouped by engine.

**Response**: `AvailableModelsByEngineResponse`
```json
{
  "models_by_engine": {
    "internal": [...],
    "claude_code": [...],
    "gemini_cli": [...]
  }
}
```

### Conversation Model Update Endpoint

#### PUT /api/conversations/{conversation_id}/model
Update model for an active conversation.

**Request**: `UpdateConversationModelRequest`
```json
{
  "model_id": "anthropic:claude-opus-4"
}
```

**Response**:
```json
{
  "conversation_id": 123,
  "agent_role": "task_implementation",
  "engine": "claude_code",
  "model_id": "anthropic:claude-opus-4",
  "updated_at": "2025-01-10T12:00:00Z"
}
```

**Validation**:
- Conversation must exist (404 if not)
- Conversation must be active (400 if archived)
- Model must be compatible with conversation's engine (400 if not)
- Model must be available (provider configured) (400 if not)

**Use Case**: User wants to switch from Sonnet to Opus mid-conversation for better quality.

## Frontend Architecture

### API Client Updates

**New Types**:
```typescript
interface AgentEngineInfo {
  engine: string
  display_name: string
  description: string
}

interface AgentEngineModelConfig {
  engine: string
  model_id: string
}

interface AgentConfigurationResponse {
  agent_role: string
  config: AgentEngineModelConfig
  available_engines: AgentEngineInfo[]
}

interface UpdateAgentConfigurationRequest {
  engine: string
  model_id: string
}

interface AvailableModelsByEngineResponse {
  models_by_engine: Record<string, ModelInfo[]>
}
```

**New API Methods**:
```typescript
class ApiClient {
  async getAgentConfiguration(agentRole: string): Promise<AgentConfigurationResponse>
  async updateAgentConfiguration(agentRole: string, request: UpdateAgentConfigurationRequest): Promise<AgentConfigurationResponse>
  async getAvailableModelsByEngine(): Promise<AvailableModelsByEngineResponse>
  async updateConversationModel(conversationId: number, request: UpdateConversationModelRequest): Promise<any>
}
```

### AgentConfigurationSelector Component

New component replacing `AgentModelSelector`:

**Features**:
- Shows engine dropdown (filtered by `available_engines` for role)
- Shows model dropdown (filtered by selected engine's models)
- Cascading behavior: changing engine updates available models
- Single API call to update both engine and model

**Data Flow**:
1. Load role configuration: `GET /api/agents/{role}/configuration`
2. Load models by engine (once): `GET /api/agents/available-models`
3. User selects engine → Filter models to show only that engine's models
4. User selects model → Call `PUT /api/agents/{role}/configuration` with both

**Component Structure**:
```typescript
function AgentConfigurationSelector({ agentRole, agentName }) {
  const [config, setConfig] = useState<AgentConfigurationResponse>()
  const [modelsByEngine, setModelsByEngine] = useState<Record<string, ModelInfo[]>>()
  const [selectedEngine, setSelectedEngine] = useState<string>()
  const [selectedModel, setSelectedModel] = useState<string>()

  // On mount: load config and models
  useEffect(() => {
    loadConfiguration()
    loadModelsByEngine()
  }, [])

  // When engine changes: update available models
  const handleEngineChange = (engine: string) => {
    setSelectedEngine(engine)
    // Filter models to show only this engine's models
  }

  // When model changes: update configuration
  const handleModelChange = async (modelId: string) => {
    await apiClient.updateAgentConfiguration(agentRole, {
      engine: selectedEngine,
      model_id: modelId
    })
  }

  return (
    <>
      <EngineDropdown engines={config.available_engines} />
      <ModelDropdown models={modelsByEngine[selectedEngine]} />
    </>
  )
}
```

### Settings View Updates

Replace `AgentModelSelector` with `AgentConfigurationSelector`:

```typescript
// OLD:
<AgentModelSelector agentType="task_implementation" agentName="..." />

// NEW:
<AgentConfigurationSelector agentRole="task_implementation" agentName="..." />
```

Load models-by-engine once at Settings view level and pass down to avoid redundant API calls.

## Conversation Lifecycle

### Task Phase Transitions

When a task transitions between phases:

```
1. User updates task status: DEFINING → PLANNING
   ↓
2. API calls TaskPhaseTransitionService.create_conversation_for_task_phase()
   ↓
3. Archive current conversation (TASK_SPECIFICATION agent)
   ↓
4. Get effective config for TASK_PLANNING role
   ↓
5. Create new conversation with config snapshot
   - agent_role: "task_planning"
   - engine: "internal" (from role default or user preference)
   - model_id: "anthropic:claude-opus-4" (from config)
   - is_active: True
```

**Result**: Clean slate for new phase with appropriate agent and configuration.

### Project Conversations

Projects maintain a single long-running conversation:

```python
# When project is created:
conversation = conversation_repo.create(
    parent_entity_type=ParentEntityType.PROJECT,
    parent_entity_id=project.id,
    agent_role=AgentRole.PROJECT,  # Always PROJECT role
    engine=effective_config.engine,  # From PROJECT role config
    model_id=effective_config.model_id,
)
```

**Characteristics**:
- Single active conversation per project (no phase transitions)
- Always uses PROJECT agent role
- Engine and model from PROJECT role configuration
- Can change model mid-conversation if desired

### Model Changes Mid-Conversation

User can change model for active conversation via future UI:

```
1. User opens conversation settings
   ↓
2. UI shows current model and compatible alternatives (same engine)
   ↓
3. User selects new model (e.g., Opus → Sonnet for cost savings)
   ↓
4. PUT /api/conversations/{id}/model
   ↓
5. Conversation.model_id updated
   ↓
6. Next message uses new model
```

**Constraints**:
- Only models compatible with conversation's engine
- Only if provider is configured
- Only for active conversations (not archived)

## Migration Strategy

### Database Migration

Migration adds `agent_role` and `model_id` columns:

```python
def upgrade():
    # 1. Add columns as nullable
    op.add_column('conversations', sa.Column('agent_role', sa.String(), nullable=True))
    op.add_column('conversations', sa.Column('model_id', sa.String(), nullable=True))

    # 2. Backfill data
    # For each conversation:
    #   - Derive agent_role from parent_entity_type + task.status (or PROJECT)
    #   - Get model_id from AgentConfig for that role

    # 3. Make columns NOT NULL
    op.alter_column('conversations', 'agent_role', nullable=False)
    op.alter_column('conversations', 'model_id', nullable=False)
```

**Backfill Logic**:
```python
for conversation in conversations:
    if conversation.parent_entity_type == ParentEntityType.PROJECT:
        agent_role = AgentRole.PROJECT
    else:  # TASK
        task = get_task(conversation.parent_entity_id)
        agent_role = get_agent_role_for_status(task.status)

    # Get effective config for role
    config = agent_config_service.get_agent_configuration(agent_role)

    # Update conversation
    conversation.agent_role = agent_role.value
    conversation.model_id = config["config"]["model_id"]
    conversation.engine = conversation.engine or AgentEngine.INTERNAL
```

### Code Migration

**Service Renaming**:
1. Rename `llm_service.py` → `agent_config_service.py`
2. Rename class `LLMService` → `AgentConfigService`
3. Update all imports and dependency injection
4. Update all method signatures to use `AgentEngineModelConfig`

**API Replacement**:
1. Remove old endpoints:
   - `GET /agents/{role}/model`
   - `PUT /agents/{role}/model`
   - `GET /agents/{role}/available-models`
2. Add new endpoints:
   - `GET /agents/{role}/configuration`
   - `PUT /agents/{role}/configuration`
   - `GET /agents/available-models`
   - `PUT /conversations/{id}/model`

**Frontend Updates**:
1. Delete `AgentModelSelector.tsx`
2. Create `AgentConfigurationSelector.tsx`
3. Update `Settings.tsx` to use new component
4. Update API client with new types and methods

## Testing Strategy

### Backend Unit Tests

**AgentConfigService** (`tests/agents/test_agent_config_service.py`):
- Test effective config resolution (selected vs default)
- Test engine validation for roles
- Test model validation for engines
- Test configuration updates
- Test models-by-engine grouping

**ConversationRepository** (`tests/db/repositories/test_conversation_repository.py`):
- Test conversation creation with all parameters
- Test model updates (valid and invalid)
- Test archiving
- Test getting active conversation

**TaskPhaseTransitionService** (`tests/services/test_task_phase_transition.py`):
- Test conversation creation for task phase
- Test archiving previous conversation
- Test agent role derivation from status
- Test config snapshot at creation time

### Backend Integration Tests

**Agents Router** (`tests/api/test_agents_router.py`):
- Test GET/PUT `/agents/{role}/configuration`
- Test GET `/agents/available-models`
- Test validation errors (invalid engine/model)
- Test role-based engine restrictions

**Conversations Router** (`tests/api/test_conversations_router.py`):
- Test PUT `/conversations/{id}/model`
- Test model compatibility validation
- Test archived conversation handling

### Frontend Tests

**AgentConfigurationSelector** (`src/components/configuration/__tests__/AgentConfigurationSelector.test.tsx`):
- Test engine selection updates available models
- Test configuration update API calls
- Test validation and error states

**Settings View** (`src/views/__tests__/Settings.test.tsx`):
- Update to use new configuration selector
- Test role-level configuration updates

## Security Considerations

### Role-Based Restrictions

The system enforces role-based engine restrictions for security:

**Why restrict engines by role?**
- **PROJECT/SPECIFICATION/PLANNING**: Modify project artifacts
  - Need tool approval to prevent accidental destructive operations
  - Internal engine provides approval workflow
  - External CLIs may auto-execute dangerous operations

- **IMPLEMENTATION**: Needs full system access
  - File operations, shell commands, git operations
  - External CLIs optimized for this (Claude Code, Gemini CLI)
  - Runs in isolated environment with clear permissions

**Validation Points**:
1. API layer: Reject invalid engine for role (400 error)
2. Service layer: Validate before saving configuration
3. Conversation creation: Only use allowed engines

### Model Validation

The system validates model availability:

1. **Engine compatibility**: Model must be in engine's `available_models` list
2. **Provider configuration**: Model's provider must have API key configured
3. **Runtime availability**: Model must be accessible at time of use

**Failure modes**:
- Invalid model for engine → 400 error with clear message
- Provider not configured → 400 error with setup instructions
- Runtime failure → Fall back to alternative model or notify user

## Future Enhancements

### Conversation Model UI

Add UI for changing model mid-conversation:
- Show current model in conversation header
- Dropdown to select alternative models (same engine)
- Real-time model switching for cost/performance optimization

### Advanced Configuration

Support more granular configuration:
- Temperature and other model parameters per role
- Custom prompts per agent role
- Fallback models if primary unavailable

### Multi-Model Conversations

Enable switching models within conversation:
- Use fast model for planning, slow model for critical steps
- Automatic model selection based on task complexity
- Cost optimization strategies

### Engine Capabilities API

Expose engine capabilities to UI:
- Show what tools each engine supports
- Guide users to best engine for their task
- Explain trade-offs between engines

## Conclusion

This architecture provides:
- **Flexibility**: Support multiple agent engines with role-based control
- **Safety**: Enforce security restrictions at role level
- **Simplicity**: Unified config structure throughout system
- **Persistence**: Config snapshots prevent mid-conversation surprises
- **Extensibility**: Easy to add new engines or models

The key insight is separating **role-level defaults** (user preferences) from **conversation-level snapshots** (immutable execution context). This ensures conversations remain consistent while allowing flexible configuration.
