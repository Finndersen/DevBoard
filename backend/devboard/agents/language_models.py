from enum import StrEnum
from typing import NamedTuple

from devboard.agents.roles import AgentRoleType


class ModelType(StrEnum):
    """Types of language models."""

    FAST = "fast"
    STANDARD = "standard"
    ADVANCED = "advanced"


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ModelSeedData(NamedTuple):
    """Seed data for populating the language_models table on first startup."""

    provider: LLMProvider
    name: str
    model_type: ModelType
    full_name: str | None = None
    bedrock_id: str | None = None
    context_window: int | None = None


# Default models used to seed the database on first startup
DEFAULT_MODELS: list[ModelSeedData] = [
    # OpenAI Models
    ModelSeedData(provider=LLMProvider.OPENAI, name="gpt-5", model_type=ModelType.STANDARD),
    ModelSeedData(provider=LLMProvider.OPENAI, name="gpt-4.1", model_type=ModelType.STANDARD, context_window=1_047_576),
    ModelSeedData(provider=LLMProvider.OPENAI, name="gpt-5-mini", model_type=ModelType.FAST),
    ModelSeedData(provider=LLMProvider.OPENAI, name="gpt-5-nano", model_type=ModelType.FAST),
    # Anthropic Models (with full names for Claude Code)
    ModelSeedData(
        provider=LLMProvider.ANTHROPIC,
        name="claude-sonnet-4.5",
        model_type=ModelType.STANDARD,
        full_name="claude-sonnet-4-5-20250929",
        context_window=200_000,
    ),
    ModelSeedData(
        provider=LLMProvider.ANTHROPIC,
        name="claude-opus-4.1",
        model_type=ModelType.ADVANCED,
        full_name="claude-opus-4-1-20250805",
        context_window=200_000,
    ),
    ModelSeedData(
        provider=LLMProvider.ANTHROPIC,
        name="claude-opus-4",
        model_type=ModelType.ADVANCED,
        full_name="claude-opus-4-20250514",
        context_window=200_000,
    ),
    ModelSeedData(
        provider=LLMProvider.ANTHROPIC,
        name="claude-sonnet-4",
        model_type=ModelType.STANDARD,
        full_name="claude-sonnet-4-20250514",
        context_window=200_000,
    ),
    ModelSeedData(
        provider=LLMProvider.ANTHROPIC,
        name="claude-haiku-4-5",
        model_type=ModelType.FAST,
        full_name="claude-haiku-4-5-20251001",
        context_window=200_000,
    ),
    # Google Models
    ModelSeedData(
        provider=LLMProvider.GOOGLE, name="gemini-2.5-pro", model_type=ModelType.STANDARD, context_window=1_048_576
    ),
    ModelSeedData(
        provider=LLMProvider.GOOGLE, name="gemini-2.5-flash", model_type=ModelType.FAST, context_window=1_048_576
    ),
    ModelSeedData(
        provider=LLMProvider.GOOGLE, name="gemini-2.5-flash-lite", model_type=ModelType.FAST, context_window=1_048_576
    ),
]


# Recommended model types for different agent roles
RECOMMENDED_AGENT_MODEL_TYPES = {
    AgentRoleType.PROJECT: ModelType.STANDARD,
    AgentRoleType.TASK_PLANNING: ModelType.ADVANCED,
    AgentRoleType.TASK_IMPLEMENTATION: ModelType.ADVANCED,
    AgentRoleType.TASK_PR_REVIEW: ModelType.STANDARD,
    AgentRoleType.CODE_REVIEW: ModelType.STANDARD,
    AgentRoleType.INVESTIGATION: ModelType.FAST,
    AgentRoleType.STEP_EXECUTION: ModelType.STANDARD,
}
