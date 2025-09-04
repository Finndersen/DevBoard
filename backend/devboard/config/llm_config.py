"""LLM provider configuration schemas for PydanticAI integration."""

from devboard.config.base import BaseConfig


class OpenAIProviderConfig(BaseConfig):
    """Configuration for OpenAI LLM provider."""

    config_key = "llm.openai.main"

    api_key: str  # From OPENAI_API_KEY env var
    organization_id: str | None = None  # From OPENAI_ORG_ID env var
    base_url: str = "https://api.openai.com/v1"

    model_config = BaseConfig.get_base_config("OPENAI_")


class AnthropicProviderConfig(BaseConfig):
    """Configuration for Anthropic LLM provider."""

    config_key = "llm.anthropic.main"

    api_key: str  # From ANTHROPIC_API_KEY env var
    base_url: str = "https://api.anthropic.com"

    model_config = BaseConfig.get_base_config("ANTHROPIC_")


class GoogleProviderConfig(BaseConfig):
    """Configuration for Google (Gemini) LLM provider."""

    config_key = "llm.google.main"

    api_key: str  # From GOOGLE_API_KEY env var
    base_url: str = "https://generativelanguage.googleapis.com"

    model_config = BaseConfig.get_base_config("GOOGLE_")


# Model hierarchies for different agent types (hardcoded per agent)
AGENT_MODEL_HIERARCHIES = {
    "qa": ["gpt-4.1", "claude-sonnet-4", "gemini-2.5-pro"],
    "planning": ["gemini-2.5-pro", "gpt-4.1", "claude-3.7-sonnet"],
    "implementation": ["claude-sonnet-4", "gpt-4.1", "gemini-2.5-flash"],
    "investigation": ["gpt-4.1-mini", "claude-3.5-haiku-20241022", "gemini-2.5-flash-lite"],
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
    "google": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
    ],
}
