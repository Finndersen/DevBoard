"""Agent engine definitions and management.

This module defines the available agent engines (execution frameworks) and their
capabilities, following the pattern established in language_models.py.

An AgentEngine represents the underlying technology/framework that powers an agent
(e.g., PydanticAI, Claude Code, Gemini CLI), which is separate from the AgentRole
(role/purpose like PROJECT, TASK_PLANNING, etc.).
"""

from dataclasses import dataclass
from enum import StrEnum

from devboard.agents.language_models import LLMProvider
from devboard.core.registry import Registry


class AgentEngine(StrEnum):
    """Available agent execution engines."""

    INTERNAL = "internal"
    CLAUDE_CODE = "claude_code"
    GEMINI_CLI = "gemini_cli"
    CODEX = "codex"


@dataclass
class AgentEngineDefinition:
    """Definition of an agent engine with its capabilities.

    Attributes:
        engine: The engine identifier
        display_name: Human-readable name for UI display
        description: Brief description of the engine's purpose
        available_provider: Single LLM provider this engine supports (None = all configured providers)
        requires_model_selection: Whether engine requires explicit model selection (False = can use engine default)
    """

    engine: AgentEngine
    display_name: str
    description: str
    available_provider: LLMProvider | None  # None means all configured providers
    requires_model_selection: bool  # False means engine can use its own default model


# Global registry of all engines with their capabilities
ALL_ENGINES: list[AgentEngineDefinition] = [
    AgentEngineDefinition(
        engine=AgentEngine.INTERNAL,
        display_name="Internal",
        description="Internal agent framework",
        available_provider=None,  # Supports all configured providers
        requires_model_selection=True,  # Must select from configured providers
    ),
    AgentEngineDefinition(
        engine=AgentEngine.CLAUDE_CODE,
        display_name="Claude Code",
        description="Anthropic's official CLI agent",
        available_provider=LLMProvider.ANTHROPIC,  # Only supports Anthropic models
        requires_model_selection=False,  # Can use Claude Code's default model
    ),
    AgentEngineDefinition(
        engine=AgentEngine.GEMINI_CLI,
        display_name="Gemini CLI",
        description="Google's Gemini command-line interface",
        available_provider=LLMProvider.GOOGLE,  # Only supports Google models
        requires_model_selection=False,  # Can use Gemini CLI's default model
    ),
    AgentEngineDefinition(
        engine=AgentEngine.CODEX,
        display_name="Codex",
        description="OpenAI's Codex CLI agent",
        available_provider=LLMProvider.OPENAI,
        requires_model_selection=False,
    ),
]


class AgentEngineRegistry(Registry[AgentEngineDefinition]):
    """Registry for querying agent engine capabilities."""

    def __init__(self, engines: list[AgentEngineDefinition]) -> None:
        super().__init__(engines, key_attr="engine")

    def get_available_engines(self) -> list[AgentEngineDefinition]:
        """Get all available engine definitions."""
        return self.list_values()


# Global default agent engine registry instance
agent_engine_registry = AgentEngineRegistry(ALL_ENGINES)
