from dataclasses import dataclass

from devboard.integrations.codebase import CodebaseIntegration


@dataclass
class BaseDeps:
    """Base context class for all agents."""

    codebase_integration: CodebaseIntegration | None = None
