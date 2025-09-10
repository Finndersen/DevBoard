"""Agent configuration schemas."""
from typing import ClassVar

from devboard.agents.types import AgentType
from devboard.config.base import BaseConfig


class AgentConfig(BaseConfig):
    """Base configuration for AI agents."""

    agent_type: ClassVar[AgentType]

    selected_model: str | None = None  # User's preferred model override

    @classmethod
    @property
    def config_key(cls) -> str:
        return f"agent.{cls.agent_type.value}.default"


class ProjectAgentConfig(AgentConfig):
    """Configuration for Project Q&A Agent."""

    agent_type = AgentType.PROJECT


# TODO: Keep these two task agents seperate or combine?
class TaskSpecificationAgentConfig(AgentConfig):
    """Configuration for Task Planning Agent."""

    agent_type = AgentType.TASK_SPECIFICATION


class PlanningAgentConfig(AgentConfig):
    """Configuration for Task Planning Agent."""

    agent_type = AgentType.TASK_PLANNING


class ImplementationAgentConfig(AgentConfig):
    """Configuration for Task Implementation Agent."""

    agent_type = AgentType.TASK_IMPLEMENTATION


class InvestigationAgentConfig(AgentConfig):
    """Configuration for Context Investigation/Gathering Agent."""

    agent_type = AgentType.INVESTIGATION
