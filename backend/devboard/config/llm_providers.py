"""LLM provider configuration schemas for PydanticAI integration."""

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


class GoogleProviderConfig(BaseConfig):
    """Configuration for Google Gemini LLM provider."""

    config_key = "llm.google.main"
    env_prefix = "GEMINI_"

    api_key: str  # From GEMINI_API_KEY env var
    base_url: str = "https://generativelanguage.googleapis.com"
