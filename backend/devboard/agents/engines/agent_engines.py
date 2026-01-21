"""Agent engine definitions and management.

This module defines the available agent engines (execution frameworks) and their
capabilities, following the pattern established in language_models.py.

An AgentEngine represents the underlying technology/framework that powers an agent
(e.g., PydanticAI, Claude Code, Gemini CLI), which is separate from the AgentRole
(role/purpose like PROJECT, TASK_SPECIFICATION, etc.).
"""

from dataclasses import dataclass
from enum import StrEnum

from devboard.agents.language_models import LLMProvider
from devboard.agents.roles import AgentRoleType
from devboard.core.registry import Registry


class AgentEngine(StrEnum):
    """Available agent execution engines."""

    INTERNAL = "internal"
    CLAUDE_CODE = "claude_code"
    GEMINI_CLI = "gemini_cli"


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
]


# Engine restrictions by agent role
# PROJECT, SPECIFICATION, and PLANNING require tool approval (PydanticAI only)
# IMPLEMENTATION can use any external engine for full capabilities
# First engine in the list is the recommended one for each role
ALLOWED_ENGINES_BY_AGENT_ROLE: dict[AgentRoleType, list[AgentEngine]] = {
    AgentRoleType.PROJECT: [AgentEngine.INTERNAL],
    AgentRoleType.TASK_SPECIFICATION: [AgentEngine.INTERNAL, AgentEngine.CLAUDE_CODE],
    AgentRoleType.TASK_PLANNING: [AgentEngine.INTERNAL, AgentEngine.CLAUDE_CODE],
    AgentRoleType.TASK_IMPLEMENTATION: [AgentEngine.CLAUDE_CODE, AgentEngine.GEMINI_CLI],
    AgentRoleType.TASK_PR_REVIEW: [AgentEngine.CLAUDE_CODE, AgentEngine.GEMINI_CLI],
    AgentRoleType.INVESTIGATION: [AgentEngine.INTERNAL, AgentEngine.CLAUDE_CODE],
}


class AgentEngineRegistry(Registry[AgentEngineDefinition]):
    """Registry for querying agent engine capabilities."""

    def __init__(self, engines: list[AgentEngineDefinition]) -> None:
        """Initialize registry with engine definitions."""
        super().__init__(engines, key_attr="engine")

    def get_available_engines_for_agent_role(self, agent_role: AgentRoleType) -> list[AgentEngineDefinition]:
        """Get all engines allowed for a given agent role.

        Args:
            agent_role: The agent role to get allowed engines for

        Returns:
            List of AgentEngineDefinition instances allowed for the agent role
        """
        allowed = ALLOWED_ENGINES_BY_AGENT_ROLE.get(agent_role, [])
        return [defn for engine in allowed if (defn := self.get(engine)) is not None]

    def get_default_engine_for_agent_role(self, agent_role: AgentRoleType) -> AgentEngine:
        """Get recommended engine for a given agent role.

        Args:
            agent_role: The agent role to get recommendation for

        Returns:
            Recommended AgentEngine for the agent role
        """
        return ALLOWED_ENGINES_BY_AGENT_ROLE[agent_role][0]

    def validate_engine_for_agent_role(self, engine: AgentEngine, agent_role: AgentRoleType) -> bool:
        """Check if engine is allowed for given agent role.

        Args:
            engine: The engine to validate
            agent_role: The agent role to validate against

        Returns:
            True if engine is allowed for agent role, False otherwise
        """
        allowed = ALLOWED_ENGINES_BY_AGENT_ROLE.get(agent_role, [])
        return engine in allowed

    def get_all_engines(self) -> list[AgentEngineDefinition]:
        """Get all available engine definitions.

        Returns:
            List of all AgentEngineDefinition instances
        """
        return self.list_values()


# Global default agent engine registry instance
agent_engine_registry = AgentEngineRegistry(ALL_ENGINES)
