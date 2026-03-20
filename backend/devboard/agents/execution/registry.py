"""Global registry for the ConversationExecutionManager singleton.

Provides access to the execution manager without importing the full
manager module, breaking the circular import chain:
execution/manager → factories → roles → task_tools → execution/registry.

The manager is created and registered during FastAPI lifespan startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from devboard.agents.execution.manager import ConversationExecutionManager

_instance: ConversationExecutionManager | None = None


def get_execution_manager() -> ConversationExecutionManager:
    assert _instance is not None, "ConversationExecutionManager not initialized — app lifespan not started"
    return _instance


def set_execution_manager(manager: ConversationExecutionManager) -> None:
    global _instance
    _instance = manager
