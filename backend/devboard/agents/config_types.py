"""Configuration type definitions for agents.

This module contains type definitions that are used across the agent system,
separated to avoid circular import issues.
"""

from pydantic import BaseModel

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.language_models import LLMProvider, ModelType


class AgentEngineModelConfig(BaseModel):
    """Combined engine and model configuration.

    This structure is used throughout the system to represent an agent's
    execution engine and the model it uses. Engine and model form a cohesive
    unit that must be validated together.

    Attributes:
        engine: The agent execution engine (INTERNAL, CLAUDE_CODE, GEMINI_CLI)
        model_id: Model identifier in "provider:model" format (e.g., "anthropic:claude-sonnet-4")
                  or None to use engine's default model
    """

    engine: AgentEngine
    model_id: str | None


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


class AgentEngineInfo(BaseModel):
    """Information about an agent engine.

    Attributes:
        engine: The agent execution engine value (e.g., "internal", "claude_code")
        display_name: Human-readable name for display in UI
        description: Description of what the engine does
        requires_model_selection: Whether this engine requires explicit model selection
    """

    engine: AgentEngine
    display_name: str
    description: str
    requires_model_selection: bool
