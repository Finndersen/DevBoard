from enum import StrEnum

from pydantic import BaseModel


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ModelType(StrEnum):
    """Types of language models."""

    REASONING = "reasoning"
    FAST = "fast"


class AgentEngine(StrEnum):
    """Available agent execution engines."""

    INTERNAL = "internal"
    CLAUDE_CODE = "claude_code"
    GEMINI_CLI = "gemini_cli"


class AgentRole(StrEnum):
    """Available agent roles in the system.

    Each role represents a specific responsibility or function that an agent
    can fulfill, such as project management, task planning, or implementation.
    """

    PROJECT = "project"
    # TODO: Keep these two task agents seperate or combine?
    TASK_SPECIFICATION = "task_specification"
    TASK_PLANNING = "task_planning"
    TASK_IMPLEMENTATION = "task_implementation"
    INVESTIGATION = "investigation"


class AgentEngineModelConfig(BaseModel):
    """Combined engine and model configuration.

    This structure is used throughout the system to represent an agent's
    execution engine and the model it uses. Engine and model form a cohesive
    unit that must be validated together.

    Attributes:
        engine: The agent execution engine (INTERNAL, CLAUDE_CODE, GEMINI_CLI)
        model_id: Model identifier in "provider:model" format (e.g., "anthropic:claude-sonnet-4")
    """

    engine: AgentEngine
    model_id: str


class AgentEngineInfo(BaseModel):
    """Information about an agent engine.

    Attributes:
        engine: The agent execution engine value (e.g., "internal", "claude_code")
        display_name: Human-readable name for display in UI
        description: Description of what the engine does
    """

    engine: AgentEngine
    display_name: str
    description: str


class ModelInfo(BaseModel):
    """Information about a language model.

    Attributes:
        id: Model identifier in "provider:model" format (e.g., "anthropic:claude-sonnet-4.5")
        provider: The LLM provider (e.g., anthropic, openai, google)
        name: Human-readable model name
        model_type: Type of model (reasoning or fast)
    """

    id: str
    provider: LLMProvider
    name: str
    model_type: ModelType


class AgentConfiguration(BaseModel):
    """Complete agent configuration including role, config, and available options.

    Attributes:
        agent_role: The agent role this configuration applies to
        config: Current effective engine and model configuration
        available_engines: List of engines available for this agent role
    """

    agent_role: AgentRole
    config: AgentEngineModelConfig
    available_engines: list[AgentEngineInfo]


class AvailableModelsByEngine(BaseModel):
    """All available models grouped by engine.

    Attributes:
        models_by_engine: Dictionary mapping engine names to lists of models
    """

    models_by_engine: dict[str, list[ModelInfo]]
