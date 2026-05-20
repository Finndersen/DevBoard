"""Configuration type definitions for agents.

This module contains type definitions that are used across the agent system,
separated to avoid circular import issues.
"""

from pydantic import BaseModel, Field, computed_field

from devboard.agents.engines import AgentEngine
from devboard.agents.language_models import LLMProvider, ModelType
from devboard.db.models.language_model import LanguageModelDB


class AgentEngineModelInput(BaseModel):
    """Input type for setting engine and model configuration.

    Used when creating or updating agent configuration via API or service calls.

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
        model_type: Type of model (fast, standard, or advanced)
    """

    id: str
    provider: LLMProvider
    name: str
    model_type: ModelType


class AgentEngineModelConfig(BaseModel):
    """Resolved engine and model configuration.

    Returned by get_effective_config() with the model already resolved from
    the registry. Consumers can access the full LanguageModel directly.

    Attributes:
        engine: The agent execution engine (INTERNAL, CLAUDE_CODE, GEMINI_CLI)
        model_db: Resolved LanguageModel instance, or None for engines that
                  don't require model selection
    """

    model_config = {"arbitrary_types_allowed": True}

    engine: AgentEngine
    model_db: LanguageModelDB | None = Field(exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def model(self) -> ModelInfo | None:
        if self.model_db is None:
            return None
        return ModelInfo(
            id=self.model_db.model_id,
            provider=self.model_db.provider,
            name=self.model_db.name,
            model_type=self.model_db.model_type,
        )


class AgentEngineInfo(BaseModel):
    """Information about an agent engine.

    Attributes:
        engine: The agent execution engine value (e.g., "internal", "claude_code")
        display_name: Human-readable name for display in UI
        description: Description of what the engine does
        requires_model_selection: Whether this engine requires explicit model selection
        is_available: Whether the engine is currently available for use
        unavailable_reason: Explanation of why engine is unavailable (if is_available is False)
    """

    engine: AgentEngine
    display_name: str
    description: str
    requires_model_selection: bool
    is_available: bool = True
    unavailable_reason: str | None = None
