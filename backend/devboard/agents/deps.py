from dataclasses import dataclass

from devboard.services.context_assembly import ContextAssemblyService


@dataclass
class BaseDeps:
    """Base context class for all agents."""

    context_service: ContextAssemblyService
