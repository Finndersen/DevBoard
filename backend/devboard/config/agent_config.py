"""Agent configuration schemas."""

from typing import ClassVar

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.role_types import AgentRoleType
from devboard.config.base import BaseConfig


class AgentConfig(BaseConfig):
    """Base configuration for AI agents.

    Attributes:
        agent_type: Type/role of the agent (PROJECT, TASK_SPECIFICATION, etc.)
        selected_engine: User's preferred agent engine override (PydanticAI, Claude Code, etc.)
        selected_model: User's preferred model override (provider:model format)
    """

    agent_type: ClassVar[AgentRoleType]

    selected_engine: AgentEngine | None = None  # User's preferred engine override
    selected_model: str | None = None  # User's preferred model override

    @classmethod
    @property  # type: ignore[misc]
    def config_key(cls) -> str:  # type: ignore[misc,override]
        return f"agent.{cls.agent_type.value}.default"


class ProjectAgentConfig(AgentConfig):
    """Configuration for Project Q&A Agent."""

    agent_type = AgentRoleType.PROJECT


# TODO: Keep these two task agents seperate or combine?
class TaskSpecificationAgentConfig(AgentConfig):
    """Configuration for Task Planning Agent."""

    agent_type = AgentRoleType.TASK_SPECIFICATION


class TaskPlanningAgentConfig(AgentConfig):
    """Configuration for Task Planning Agent."""

    agent_type = AgentRoleType.TASK_PLANNING


class TaskImplementationAgentConfig(AgentConfig):
    """Configuration for Task Implementation Agent."""

    agent_type = AgentRoleType.TASK_IMPLEMENTATION


class InvestigationAgentConfig(AgentConfig):
    """Configuration for Context Investigation/Gathering Agent."""

    agent_type = AgentRoleType.INVESTIGATION
