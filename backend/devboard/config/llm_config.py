"""LLM provider configuration schemas for PydanticAI integration."""

from devboard.agents.types import AgentType
from devboard.config.base import BaseConfig


class OpenAIProviderConfig(BaseConfig):
    """Configuration for OpenAI LLM provider."""

    config_key = "llm.openai.main"
    env_prefix = "OPENAI_"

    api_key: str  # From OPENAI_API_KEY env var
    organization_id: str | None = None  # From OPENAI_ORG_ID env var
    base_url: str = "https://api.openai.com/v1"


class AnthropicProviderConfig(BaseConfig):
    """Configuration for Anthropic LLM provider."""

    config_key = "llm.anthropic.main"
    env_prefix = "ANTHROPIC_"

    api_key: str  # From ANTHROPIC_API_KEY env var
    base_url: str = "https://api.anthropic.com"


class GeminiProviderConfig(BaseConfig):
    """Configuration for Gemini LLM provider."""

    config_key = "llm.gemini.main"
    env_prefix = "GEMINI_"

    api_key: str  # From GEMINI_API_KEY env var
    base_url: str = "https://generativelanguage.googleapis.com"


# Model hierarchies for different agent types (hardcoded per agent)
AGENT_MODEL_HIERARCHIES = {
    AgentType.PROJECT: ["gemini-2.5-pro", "gpt-4.1", "claude-sonnet-4"],
    AgentType.TASK_SPECIFICATION: ["gemini-2.5-pro", "gpt-4.1", "claude-sonnet-4"],
    AgentType.TASK_PLANNING: ["gemini-2.5-pro", "gpt-4.1", "claude-3.7-sonnet"],
    AgentType.TASK_IMPLEMENTATION: ["claude-sonnet-4", "gpt-4.1", "gemini-2.5-flash"],
    AgentType.INVESTIGATION: [
        "gpt-4.1-mini",
        "claude-3.5-haiku-20241022",
        "gemini-2.5-flash-lite",
    ],
}


# Available models per provider (latest 2024-2025 models)
PROVIDER_MODELS = {
    "openai": [
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "o4-mini",
    ],
    "anthropic": [
        "claude-sonnet-4",
        "claude-opus-4",
        "claude-3.7-sonnet",
        "claude-3.5-sonnet-20241022",
        "claude-3.5-haiku-20241022",
    ],
    "gemini": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
    ],
}
