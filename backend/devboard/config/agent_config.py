"""Agent configuration schemas."""

from devboard.config.base import BaseConfig


class AgentConfig(BaseConfig):
    """Base configuration for AI agents."""

    selected_model: str | None = None  # User's preferred model override

    model_config = BaseConfig.get_base_config("AGENT_")


class QAAgentConfig(AgentConfig):
    """Configuration for Project Q&A Agent."""

    config_key = "agent.qa.default"


class PlanningAgentConfig(AgentConfig):
    """Configuration for Task Planning Agent."""

    config_key = "agent.planning.default"


class ImplementationAgentConfig(AgentConfig):
    """Configuration for Task Implementation Agent."""

    config_key = "agent.implementation.default"

    enable_code_execution: bool = True


class InvestigationAgentConfig(AgentConfig):
    """Configuration for Context Investigation/Gathering Agent."""

    config_key = "agent.investigation.default"
