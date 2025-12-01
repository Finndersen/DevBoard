"""Agent roles package.

This package contains the base Role class and role implementations.

Import patterns:
- Base class and type enum: from devboard.agents.roles import Role, AgentRoleType
- Role implementations: from devboard.agents.roles.<role_name> import <RoleClass>
"""

from .base import AgentRole
from .role_types import AgentRoleType

__all__ = [
    "AgentRoleType",
    "AgentRole",
]
