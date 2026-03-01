"""Database models package."""

from .agent_role_config import AgentRoleConfig
from .base import Base
from .codebase import BranchHandling, Codebase, MergeMethod, MergeStrategy
from .configuration import Configuration, ContextProviderResource
from .conversation import Conversation
from .custom_field import CustomFieldDefinition, CustomFieldType
from .document import Document, DocumentType
from .enums import EntityType, ParentEntityType
from .mcp_server import (
    HttpMCPConfig,
    MCPServerConfig,
    MCPServerType,
    MCPTool,
    StdioMCPConfig,
)
from .messages import ConversationMessage, MessageType
from .oauth import (
    OAuthClientInfo,
    OAuthProvider,
    OAuthProviderType,
    OAuthToken,
    PendingOAuthAuthorization,
)
from .project import Project
from .task import Task, TaskStatus
from .worktree_slot import WorktreeSlot

__all__ = [
    "AgentRoleConfig",
    "Base",
    "BranchHandling",
    "Codebase",
    "CustomFieldDefinition",
    "CustomFieldType",
    "Configuration",
    "ContextProviderResource",
    "Conversation",
    "ConversationMessage",
    "Document",
    "DocumentType",
    "HttpMCPConfig",
    "MCPServerConfig",
    "MCPServerType",
    "MCPTool",
    "MergeMethod",
    "MergeStrategy",  # Deprecated alias for MergeMethod
    "MessageType",
    "OAuthClientInfo",
    "OAuthProvider",
    "OAuthProviderType",
    "OAuthToken",
    "EntityType",
    "ParentEntityType",
    "PendingOAuthAuthorization",
    "Project",
    "StdioMCPConfig",
    "Task",
    "TaskStatus",
    "WorktreeSlot",
]
