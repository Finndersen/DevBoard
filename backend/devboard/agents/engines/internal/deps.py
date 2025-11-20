from dataclasses import dataclass

from devboard.integrations.filesystem import FilesystemIntegration


@dataclass
class BaseDeps:
    """Base context class for all agents."""

    codebase_integration: FilesystemIntegration | None = None
